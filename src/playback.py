"""Anarchy Radio FM Playback Controller — streaming, effects, crossfade."""

import math
import threading
import numpy as np
from pydub import AudioSegment
from pydub.utils import make_chunks
import pyaudio
from pedalboard import (Pedalboard, HighpassFilter, LowpassFilter, Compressor,
                        Gain, Reverb, LowShelfFilter, Chorus, Bitcrush, Delay)
import console


class PlaybackController:
    FADE_MS = 500  # Fade duration for pause/resume

    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.stop_event = threading.Event()
        self._fade_out_event = threading.Event()  # Signal graceful fade-out
        self.play_thread = None
        self.current_segment = None
        self.playback_position = 0
        self.is_playing = False

        # Callbacks set by the engine
        self._on_track_finished = None
        self._get_volume = None

    def start(self, segment, on_track_finished=None, get_volume=None, fade_in=False):
        """Start streaming an AudioSegment on a new thread."""
        console.debug(f"playback.start() — is_playing={self.is_playing}, thread_alive={self.play_thread and self.play_thread.is_alive()}, stop_event={self.stop_event.is_set()}")
        # Kill any lingering thread before starting fresh
        if self.play_thread and self.play_thread.is_alive():
            console.debug("playback.start() — killing lingering thread")
            self.stop_event.set()
            self.play_thread.join(timeout=2)

        if fade_in and len(segment) > self.FADE_MS:
            segment = segment.fade_in(self.FADE_MS)
        self.current_segment = segment
        self.playback_position = 0
        self.is_playing = True
        self.stop_event.clear()
        self._fade_out_event.clear()
        self._on_track_finished = on_track_finished
        self._get_volume = get_volume
        self.play_thread = threading.Thread(target=self._stream_audio, name="AudioStream")
        self.play_thread.start()
        console.debug(f"playback.start() — stream thread launched, is_playing=True")

    def stop(self, fade_out=False):
        """Stop current playback, optionally with a fade-out."""
        console.debug(f"playback.stop(fade={fade_out}) — is_playing={self.is_playing}, thread_alive={self.play_thread and self.play_thread.is_alive()}")
        self.is_playing = False
        if fade_out and self.play_thread and self.play_thread.is_alive():
            # Signal fade-out, then wait for it to complete
            self._fade_out_event.set()
            t = self.play_thread
            if t is not None and t is not threading.current_thread():
                t.join(timeout=self.FADE_MS / 1000.0 + 2)
        else:
            self.stop_event.set()
            t = self.play_thread
            if t is not None and t.is_alive() and t is not threading.current_thread():
                t.join(timeout=5)
        console.debug(f"playback.stop() — done, is_playing={self.is_playing}, stop_event={self.stop_event.is_set()}")

    def _stream_audio(self):
        chunk_length = 50
        fade_chunks = max(1, self.FADE_MS // chunk_length)
        try:
            segment = self.current_segment
            if segment is None:
                console.warn("No audio segment loaded!")
                return

            chunks = make_chunks(segment, chunk_length)
            console.faint(f"Stream: {len(chunks)} chunks ({len(segment)}ms)")

            self.stream = self.p.open(
                format=self.p.get_format_from_width(segment.sample_width),
                channels=segment.channels,
                rate=segment.frame_rate,
                output=True
            )

            self.playback_position = 0
            fade_counter = -1  # -1 = not fading
            first_chunk_written = False

            for chunk in chunks:
                if self.stop_event.is_set():
                    break

                # Start fade-out if signalled
                if self._fade_out_event.is_set() and fade_counter < 0:
                    fade_counter = fade_chunks

                # Apply fade-out attenuation
                if fade_counter > 0:
                    fade_factor = fade_counter / fade_chunks
                    chunk = chunk - (40 * (1 - fade_factor))  # 40dB range for smooth fade
                    fade_counter -= 1
                    if fade_counter <= 0:
                        break  # Fade complete, stop playback

                effective = 1.0
                if self._get_volume:
                    effective = self._get_volume()
                if effective <= 0.002:
                    # Fully muted — true silence, not "-20dB but audible"
                    chunk = chunk - 120
                elif effective < 1.0:
                    chunk = chunk + (20 * math.log10(effective))

                self.stream.write(chunk.raw_data)
                self.playback_position += chunk_length

                if not first_chunk_written:
                    first_chunk_written = True
                    console.debug("Audio stream active — first chunk written.")

            if self.stream is not None:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

            # Diagnostic: why did the loop end?
            if self.stop_event.is_set():
                console.debug("Stream ended: stop_event was set.")
            elif self._fade_out_event.is_set():
                console.debug("Stream ended: faded out.")
            else:
                console.debug(f"Stream ended: track finished ({self.playback_position}ms played).")

        except Exception as e:
            console.warn(f"Playback glitch: {e}")
            if self.stream is not None:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

        stopped = self.stop_event.is_set()
        faded = self._fade_out_event.is_set()
        if not stopped and not faded and self._on_track_finished:
            # Schedule on a new thread so we don't self-join the current
            # play_thread when start() is called from _advance_track.
            cb = self._on_track_finished
            threading.Thread(target=cb, daemon=True).start()

    def close(self):
        """Stop playback and release the PyAudio instance. Call on shutdown."""
        try:
            self.stop(fade_out=False)
        except Exception:
            pass
        try:
            self.p.terminate()
        except Exception:
            pass

    def capture_outgoing_tail(self, crossfade_ms):
        """Grab the remaining audio from the current track for crossfading."""
        if not self.is_playing or self.current_segment is None:
            return None
        remaining_ms = len(self.current_segment) - self.playback_position
        if remaining_ms <= 0:
            return None
        tail_start = max(self.playback_position, len(self.current_segment) - crossfade_ms)
        return self.current_segment[tail_start:]

    @staticmethod
    def crossfade_segments(outgoing_tail, incoming, crossfade_ms):
        """Blend outgoing tail into incoming track."""
        if outgoing_tail and len(outgoing_tail) > 0 and crossfade_ms > 0:
            xfade_ms = min(crossfade_ms, len(outgoing_tail), len(incoming))
            if xfade_ms > 100:
                tail_faded = outgoing_tail.fade_out(xfade_ms)
                head = incoming[:xfade_ms].fade_in(xfade_ms)
                rest = incoming[xfade_ms:]
                return tail_faded.overlay(head) + rest
        return incoming

    @staticmethod
    def apply_effects(segment, use_radio, use_reverb, fx_params):
        """Apply pedalboard FX chain to an AudioSegment. Returns processed segment.

        Per-state toggles: radio, reverb
        Global params (active when non-default): bass boost, chorus, bitcrush, echo
        """
        # Check if any effect is actually active
        bass = fx_params.get("bassboost", 0)
        chorus_depth = fx_params.get("chorusdepth", 0)
        bitcrush_bits = fx_params.get("bitcrush", 16)
        echo_delay = fx_params.get("echodelay", 0)

        has_global_fx = (bass > 0 or chorus_depth > 0 or bitcrush_bits < 16 or echo_delay > 0)
        if not use_radio and not use_reverb and not has_global_fx:
            return segment

        effects = []
        fx_names = []

        # --- Per-state effects ---
        if use_radio:
            hp = max(20, fx_params.get("radiohighpass", 500))
            lp = max(hp + 100, fx_params.get("radiolowpass", 4500))
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=float(hp)),
                LowpassFilter(cutoff_frequency_hz=float(lp)),
                Compressor(threshold_db=-20, ratio=4.0),
                Gain(gain_db=3),
            ])
            fx_names.append(f"Radio({hp}-{lp}Hz)")

        # --- Global effects (active when param != default) ---
        if bass > 0:
            effects.append(LowShelfFilter(cutoff_frequency_hz=200.0, gain_db=float(bass)))
            fx_names.append(f"Bass(+{bass}dB)")

        if chorus_depth > 0:
            rate = max(0.1, fx_params.get("chorusrate", 15) / 10.0)  # 10-50 → 1.0-5.0 Hz
            depth = max(0.01, chorus_depth / 100.0)
            effects.append(Chorus(rate_hz=rate, depth=depth, mix=0.5))
            fx_names.append(f"Chorus({chorus_depth}%@{rate:.1f}Hz)")

        if bitcrush_bits < 16:
            effects.append(Bitcrush(bit_depth=float(bitcrush_bits)))
            fx_names.append(f"Bitcrush({bitcrush_bits}bit)")

        if use_reverb:
            room = max(0.0, min(1.0, fx_params.get("reverbroomsize", 90) / 100.0))
            wet = max(0.0, min(1.0, fx_params.get("reverbwet", 30) / 100.0))
            effects.append(Reverb(room_size=room, wet_level=wet, dry_level=1.0 - wet, damping=0.5))
            fx_names.append(f"Reverb(room={int(room*100)}%,wet={int(wet*100)}%)")

        if echo_delay > 0:
            echo_mix = max(0.0, min(1.0, fx_params.get("echomix", 25) / 100.0))
            delay_sec = max(0.01, echo_delay / 1000.0)
            effects.append(Delay(delay_seconds=delay_sec, feedback=0.3, mix=echo_mix))
            fx_names.append(f"Echo({echo_delay}ms,mix={int(echo_mix*100)}%)")

        board = Pedalboard(effects)

        try:
            samples = np.array(segment.get_array_of_samples()).astype(np.float32)
            samples /= 2**15

            if segment.channels == 2:
                samples = samples.reshape((-1, 2)).T
            else:
                samples = samples.reshape((1, -1))

            processed = board(samples, segment.frame_rate)

            if segment.channels == 2:
                processed = processed.T.flatten()
            else:
                processed = processed.flatten()

            processed = np.clip(processed * 2**15, -32768, 32767).astype(np.int16)

            console.debug(f"FX applied: {', '.join(fx_names)}")

            return AudioSegment(
                processed.tobytes(),
                frame_rate=segment.frame_rate,
                sample_width=2,
                channels=segment.channels,
            )
        except Exception as e:
            console.warn(f"FX processing failed, using clean audio: {e}")
            return segment
