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


def load_audio(path):
    """Decode any audio file into a 16-bit/44.1kHz/stereo AudioSegment.

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

        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().tobytes())

        # Flush whatever the resampler is still holding, or the last few
        # milliseconds of every track go missing.
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().tobytes())

    return AudioSegment(
        data=b"".join(chunks),
        sample_width=SAMPLE_WIDTH,
        frame_rate=SAMPLE_RATE,
        channels=1 if layout == "mono" else CHANNELS,
    )
