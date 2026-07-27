"""Audio file decoding via PyAV — replaces pydub's ffmpeg subprocess path.

pydub decodes by shelling out to `ffmpeg`/`ffprobe`, which meant every user
had to install ffmpeg and put it on their PATH before .mp3/.ogg would play.
PyAV ships ffmpeg's libraries *inside the wheel*, so the decoder rides along
in the build and there's nothing for the user to install.

Three things fall out of that, beyond the obvious convenience:

  * No subprocess per track — decoding happens in-process, so there's no
    console window to suppress and no process spawn latency on state changes.
  * No ffprobe round-trip. pydub calls `mediainfo_json()` on every
    `from_file()`, which is a second process launch just to sniff the format.
  * One canonical output format. Everything comes back 16-bit / 44100 Hz /
    stereo, which is what PyAudio needs anyway (see XiPodEngine._normalize
    for why odd sample widths used to produce silence on some devices).

pydub is still very much in use — AudioSegment slicing, crossfades, silence
and the FX chain all stay. This module only replaces the *loading* step.
"""

import av

from pydub import AudioSegment

# What PyAudio wants, and what the FX chain assumes. Kept in sync with
# XiPodEngine._normalize, which is a no-op for anything loaded through here.
SAMPLE_RATE = 44100
SAMPLE_WIDTH = 2   # bytes — 16-bit signed
CHANNELS = 2


def probe_duration_ms(path):
    """Track length in milliseconds, read from container metadata.

    Costs a file open and a header read — no decoding. That's the whole point:
    Radio Mode needs a duration to pick a random start position, and decoding
    an hour-long station rip just to measure it is exactly what we're avoiding.
    Returns 0 if the container doesn't report a duration.
    """
    try:
        with av.open(path) as container:
            if container.duration:
                return int(container.duration / av.time_base * 1000)
            if container.streams.audio:
                stream = container.streams.audio[0]
                if stream.duration and stream.time_base:
                    return int(stream.duration * stream.time_base * 1000)
    except Exception:
        pass
    return 0


def load_audio(path, start_ms=0, max_ms=0):
    """Decode an audio file into a 16-bit/44.1kHz/stereo AudioSegment.

    `start_ms` seeks before decoding rather than decoding everything and
    slicing after. For Radio Mode that's the difference between usable and
    not: a 65-minute station rip is ~657 MB of PCM and takes seconds to
    decode, and dropping in 40 minutes deep used to mean decoding all 65 and
    binning the first 40.

    `max_ms` stops after that much audio (0 = no limit). Radio Mode uses it to
    bound both the wait and the memory: without a cap, an hour-long station is
    ~657 MB of PCM and over ten seconds of silence before the first note.

    Raises on unreadable or audio-less files — callers already handle that
    (every _prepare_segment call site catches and skips the bad track).
    """
    chunks = []

    with av.open(path) as container:
        if not container.streams.audio:
            raise ValueError("no audio stream in file")
        stream = container.streams.audio[0]
        # Let ffmpeg pick its own threading — decoding a long track is the
        # slowest thing the loader thread does.
        stream.thread_type = "AUTO"

        # Mono stays mono here and gets widened by XiPodEngine._normalize,
        # which duplicates the channel at full gain. Letting swresample do it
        # instead would cost 3 dB: its mono->stereo rematrix preserves total
        # power rather than per-channel level, so mono tracks would play
        # noticeably quieter than they did on the old pydub/ffmpeg path.
        # Anything with 2+ channels goes straight to stereo, so 5.1 sources
        # get a proper downmix rather than pydub's channel arithmetic.
        layout = "mono" if stream.channels == 1 else "stereo"
        resampler = av.AudioResampler(format="s16", layout=layout, rate=SAMPLE_RATE)

        if start_ms > 0:
            # Container seek takes microseconds. It lands on the nearest
            # packet boundary rather than the exact sample, which is neither
            # here nor there when the position was picked at random anyway.
            try:
                container.seek(int(start_ms * 1000))
            except Exception:
                pass  # unseekable container — fall back to decoding from 0

        channels = 1 if layout == "mono" else CHANNELS
        limit_bytes = 0
        if max_ms > 0:
            limit_bytes = (int(max_ms / 1000.0 * SAMPLE_RATE)
                           * SAMPLE_WIDTH * channels)

        collected = 0
        hit_limit = False
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                data = out.to_ndarray().tobytes()
                chunks.append(data)
                collected += len(data)
            if limit_bytes and collected >= limit_bytes:
                hit_limit = True
                break

        if not hit_limit:
            # Flush whatever the resampler is still holding, or the last few
            # milliseconds of every track go missing. Pointless when we've
            # stopped early — there's more file left than we asked for.
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray().tobytes())

    data = b"".join(chunks)
    if limit_bytes and len(data) > limit_bytes:
        # Trim to a whole frame so the segment isn't left with a partial sample.
        frame_bytes = SAMPLE_WIDTH * channels
        data = data[:limit_bytes - (limit_bytes % frame_bytes)]

    return AudioSegment(
        data=data,
        sample_width=SAMPLE_WIDTH,
        frame_rate=SAMPLE_RATE,
        channels=channels,
    )
