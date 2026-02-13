"""
paparapa_tts - Subtitle-to-TTS audio track generator for video files.

Takes a video file with embedded subtitles, generates a TTS audio track
timed to the subtitle cues, and muxes it into a new output file.
"""

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Force UTF-8 output on Windows so filenames with special chars don't crash
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import wave

import comtypes.client
import numpy as np
import pysubs2

# ---------------------------------------------------------------------------
# Resolve ffmpeg / ffprobe paths
# ---------------------------------------------------------------------------

def _find_ffmpeg_bin(name: str) -> str:
    """Return the full path to an ffmpeg binary, searching common locations."""
    from shutil import which
    found = which(name)
    if found:
        return found

    # Winget default install location
    appdata = os.environ.get("LOCALAPPDATA", "")
    if appdata:
        winget_dir = Path(appdata) / "Microsoft" / "WinGet" / "Packages"
        if winget_dir.exists():
            for pkg in winget_dir.iterdir():
                if "FFmpeg" in pkg.name:
                    candidate = pkg / "ffmpeg-8.0.1-full_build" / "bin" / f"{name}.exe"
                    if candidate.exists():
                        return str(candidate)
                    for subdir in pkg.iterdir():
                        candidate = subdir / "bin" / f"{name}.exe"
                        if candidate.exists():
                            return str(candidate)

    return name


FFMPEG = _find_ffmpeg_bin("ffmpeg")
FFPROBE = _find_ffmpeg_bin("ffprobe")


# ---------------------------------------------------------------------------
# Step 1 - Discover subtitle tracks
# ---------------------------------------------------------------------------

def get_audio_tracks(video_path: str) -> list[dict]:
    """Return a list of audio stream info dicts from the video file."""
    result = subprocess.run(
        [FFPROBE, "-v", "error",
         "-select_streams", "a",
         "-show_entries", "stream=index,codec_name,channels,sample_rate",
         "-show_entries", "stream_tags=language,title",
         "-of", "json",
         video_path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return data.get("streams", [])


def get_subtitle_tracks(video_path: str) -> list[dict]:
    """Return a list of subtitle stream info dicts from the video file."""
    result = subprocess.run(
        [FFPROBE, "-v", "error",
         "-select_streams", "s",
         "-show_entries", "stream=index,codec_name,codec_type",
         "-show_entries", "stream_tags=language,title,NUMBER_OF_FRAMES",
         "-of", "json",
         video_path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return data.get("streams", [])


BITMAP_SUB_CODECS = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}


def pick_subtitle_track(tracks: list[dict]) -> int:
    """Pick the subtitle track with the most frames (biggest = full dialogue)."""
    best_index = tracks[0]["index"]
    best_frames = 0
    for t in tracks:
        nf = int(t.get("tags", {}).get("NUMBER_OF_FRAMES", 0))
        if nf > best_frames:
            best_frames = nf
            best_index = t["index"]
    return best_index


def get_video_duration(video_path: str) -> float:
    """Return video duration in seconds."""
    result = subprocess.run(
        [FFPROBE, "-v", "error",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1",
         video_path],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())

# ---------------------------------------------------------------------------
# Step 2 - Extract and parse subtitles
# ---------------------------------------------------------------------------

def extract_subtitles(video_path: str, stream_index: int, tmpdir: str) -> str:
    """Extract a subtitle stream to an SRT file, return its path."""
    out_path = os.path.join(tmpdir, "subs.srt")
    subprocess.run(
        [FFMPEG, "-y", "-v", "error",
         "-i", video_path,
         "-map", f"0:{stream_index}",
         out_path],
        check=True,
    )
    return out_path


def parse_subtitles(sub_path: str) -> list[dict]:
    """Parse subtitle file into a list of {start_ms, end_ms, text} dicts."""
    subs = pysubs2.load(sub_path)
    events = []
    for line in subs:
        if line.is_comment:
            continue
        text = line.plaintext.strip()
        if not text:
            continue
        events.append({
            "start_ms": line.start,
            "end_ms": line.end,
            "text": text,
        })
    return events

# ---------------------------------------------------------------------------
# Step 3 - TTS via Windows SAPI COM
# ---------------------------------------------------------------------------

# SAPI audio format constants
SAFT22kHz16BitMono = 22
SSFM_CREATE_FOR_WRITE = 3


def list_sapi_voices() -> list[str]:
    """Return available SAPI voice names."""
    sapi = comtypes.client.CreateObject("SAPI.SpVoice")
    voices = sapi.GetVoices()
    return [voices.Item(i).GetDescription() for i in range(voices.Count)]


def create_sapi_voice(voice_name: str | None, rate: int):
    """Create a SAPI SpVoice COM object with the given voice and rate."""
    sapi = comtypes.client.CreateObject("SAPI.SpVoice")

    if voice_name:
        voices = sapi.GetVoices()
        matched = False
        for i in range(voices.Count):
            desc = voices.Item(i).GetDescription()
            if voice_name.lower() in desc.lower():
                sapi.Voice = voices.Item(i)
                matched = True
                break
        if not matched:
            print(f"Warning: voice '{voice_name}' not found. Available voices:")
            for i in range(voices.Count):
                print(f"  - {voices.Item(i).GetDescription()}")
            print("Using default voice.")

    # SAPI rate is -10 to 10. Map WPM roughly: 175 WPM ~= 0, each +-25 WPM ~= +-1
    sapi_rate = max(-10, min(10, round((rate - 175) / 25)))
    sapi.Rate = sapi_rate

    return sapi


def generate_tts_clip(sapi, text: str, filepath: str):
    """Generate a single TTS clip to a WAV file using SAPI COM."""
    stream = comtypes.client.CreateObject("SAPI.SpFileStream")
    fmt = comtypes.client.CreateObject("SAPI.SpAudioFormat")
    fmt.Type = SAFT22kHz16BitMono
    stream.Format = fmt
    stream.Open(filepath, SSFM_CREATE_FOR_WRITE)
    sapi.AudioOutputStream = stream
    sapi.Speak(text, 0)
    stream.Close()


SAMPLE_RATE = 22050  # matches SAFT22kHz16BitMono


def read_wav_samples(clip_path: str) -> np.ndarray:
    """Read a 16-bit mono WAV file into a numpy int16 array."""
    with wave.open(clip_path, "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def speed_up_samples(samples: np.ndarray, speed_factor: float) -> np.ndarray:
    """Speed up audio by resampling (simple linear interpolation)."""
    old_len = len(samples)
    new_len = int(old_len / speed_factor)
    indices = np.linspace(0, old_len - 1, new_len)
    return np.interp(indices, np.arange(old_len), samples.astype(np.float64)).astype(np.int16)


def fit_clip_samples(samples: np.ndarray, window_ms: int) -> np.ndarray:
    """
    Speed up clip samples if longer than the subtitle window.
    Returns samples that fit within window_ms.
    """
    window_samples = int(SAMPLE_RATE * window_ms / 1000)
    if len(samples) <= window_samples or window_ms < 200:
        return samples

    speed_factor = len(samples) / window_samples
    speed_factor = min(speed_factor, 3.0)  # cap to keep speech intelligible
    sped = speed_up_samples(samples, speed_factor)

    if len(sped) > window_samples:
        sped = sped[:window_samples]

    return sped

# ---------------------------------------------------------------------------
# Step 4 - Assemble full TTS audio track (with overlap mixing)
# ---------------------------------------------------------------------------

def assemble_tts_track(events: list[dict], sapi,
                       total_duration_ms: int, tmpdir: str,
                       volume: int = 100) -> str:
    """
    Generate TTS for every subtitle event and place each clip at its
    correct timestamp on a numpy int32 canvas. Overlapping clips are summed
    (mixed). Returns path to the assembled WAV file.
    """
    total_samples = int(SAMPLE_RATE * total_duration_ms / 1000)
    # Use int32 to avoid clipping when overlapping clips are summed
    canvas = np.zeros(total_samples, dtype=np.int32)

    total = len(events)
    for i, evt in enumerate(events):
        if (i + 1) % 50 == 0 or i == 0 or i == total - 1:
            pct = (i + 1) / total * 100
            print(f"\r  Processing clips: {i + 1}/{total} ({pct:.0f}%)", end="", flush=True)

        text = evt["text"]
        start_ms = evt["start_ms"]
        window = evt["end_ms"] - evt["start_ms"]

        clip_path = os.path.join(tmpdir, f"clip_{i:05d}.wav")
        try:
            generate_tts_clip(sapi, text, clip_path)
        except Exception as e:
            print(f"\n  Warning: TTS failed for clip {i}: {e}")
            continue

        if not os.path.exists(clip_path) or os.path.getsize(clip_path) < 100:
            continue

        try:
            samples = read_wav_samples(clip_path)
            samples = fit_clip_samples(samples, window)
        except Exception as e:
            print(f"\n  Warning: failed to process clip {i}: {e}")
            continue

        # Place on canvas at the correct sample offset
        start_sample = int(SAMPLE_RATE * start_ms / 1000)
        end_sample = min(start_sample + len(samples), total_samples)
        clip_len = end_sample - start_sample
        scaled = (samples[:clip_len].astype(np.int32) * volume) // 100
        canvas[start_sample:end_sample] += scaled

        os.remove(clip_path)

    print()

    # Clip to int16 range
    canvas = np.clip(canvas, -32768, 32767).astype(np.int16)

    # Write out as WAV
    out_path = os.path.join(tmpdir, "tts_track.wav")
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(canvas.tobytes())

    return out_path

# ---------------------------------------------------------------------------
# Step 5 - Mux TTS track into new video file
# ---------------------------------------------------------------------------

def mix_audio_tracks(original_video: str, tts_wav_path: str,
                     tmpdir: str, audio_stream_index: int = 0) -> str:
    """Extract original audio, mix with TTS in numpy, return path to mixed WAV."""
    # Extract original audio to WAV
    orig_wav = os.path.join(tmpdir, "original_audio.wav")
    print(f"  Extracting audio stream 0:a:{audio_stream_index}...")
    subprocess.run(
        [FFMPEG, "-y", "-v", "error",
         "-i", original_video,
         "-map", f"0:a:{audio_stream_index}",
         "-ar", str(SAMPLE_RATE),  # resample to match TTS
         "-ac", "1",               # downmix to mono for mixing
         orig_wav],
        check=True,
    )

    print("  Mixing original + TTS in memory...")
    orig_samples = read_wav_samples(orig_wav)
    tts_samples = read_wav_samples(tts_wav_path)

    # Pad shorter array to match longer
    max_len = max(len(orig_samples), len(tts_samples))
    if len(orig_samples) < max_len:
        orig_samples = np.pad(orig_samples, (0, max_len - len(orig_samples)))
    if len(tts_samples) < max_len:
        tts_samples = np.pad(tts_samples, (0, max_len - len(tts_samples)))

    # Mix: sum in int32 then clip
    mixed = orig_samples.astype(np.int32) + tts_samples.astype(np.int32)
    mixed = np.clip(mixed, -32768, 32767).astype(np.int16)

    mixed_wav = os.path.join(tmpdir, "mixed_audio.wav")
    with wave.open(mixed_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(mixed.tobytes())

    os.remove(orig_wav)
    return mixed_wav


def mux_tts_track(video_path: str, tts_audio_path: str, output_path: str,
                  tmpdir: str, audio_stream_index: int = 0,
                  track_name: str = "English (TTS)"):
    """Pre-encode all audio tracks, then mux with pure -c copy."""
    # Create mixed track
    mixed_wav = mix_audio_tracks(video_path, tts_audio_path, tmpdir,
                                audio_stream_index)

    # Encode both new tracks to AAC
    mixed_aac = os.path.join(tmpdir, "mixed.m4a")
    tts_aac = os.path.join(tmpdir, "tts_only.m4a")

    print("  Encoding audio tracks to AAC...")
    subprocess.run(
        [FFMPEG, "-y", "-v", "error",
         "-i", mixed_wav,
         "-c:a", "aac", "-b:a", "192k",
         mixed_aac],
        check=True,
    )
    subprocess.run(
        [FFMPEG, "-y", "-v", "error",
         "-i", tts_audio_path,
         "-c:a", "aac", "-b:a", "64k", "-ac", "1",
         tts_aac],
        check=True,
    )

    os.remove(mixed_wav)

    # Final mux: everything is -c copy, no filters
    print(f"  Muxing into: {output_path}")
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-stats",
         "-i", video_path,
         "-i", mixed_aac,
         "-i", tts_aac,
         "-map", "0:v",         # video
         "-map", "0:a",         # track 1: original audio
         "-map", "1:a",         # track 2: mixed (original+TTS)
         "-map", "2:a",         # track 3: TTS only
         "-map", "0:s?",        # subtitles (fonts dropped - muxer can't handle them with new streams)
         "-c", "copy",          # everything is pre-encoded, just copy
         "-metadata:s:a:1", f"title={track_name}",
         "-metadata:s:a:1", "language=eng",
         "-metadata:s:a:2", f"title={track_name} (Voice Only)",
         "-metadata:s:a:2", "language=eng",
         output_path],
        check=True,
    )

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a TTS audio track from embedded subtitles.",
    )
    parser.add_argument("input", help="Path to the input video file.")
    parser.add_argument("-o", "--output", help="Output file path. Defaults to <input>_tts.mkv")
    parser.add_argument("-v", "--voice", default=None,
                        help="TTS voice name substring (e.g. 'David', 'Zira'). Default: system default.")
    parser.add_argument("-r", "--rate", type=int, default=175,
                        help="TTS speech rate in words per minute (default: 175).")
    parser.add_argument("--volume", type=int, default=100,
                        help="TTS volume as a percentage (default: 100). 50 = half, 200 = double.")
    parser.add_argument("-a", "--audio", type=int, default=None,
                        help="Audio track number to mix TTS over (0-based). Default: first track.")
    parser.add_argument("-s", "--sub-index", type=int, default=None,
                        help="Subtitle track number to use (0-based). Default: auto-pick largest track.")
    parser.add_argument("--track-name", default="English (TTS)",
                        help="Name for the new audio track (default: 'English (TTS)').")
    parser.add_argument("--list-voices", action="store_true",
                        help="List available TTS voices and exit.")
    parser.add_argument("--list-tracks", action="store_true",
                        help="List audio and subtitle tracks and exit.")

    args = parser.parse_args()

    if args.list_voices:
        print("Available TTS voices:")
        for name in list_sapi_voices():
            print(f"  - {name}")
        return

    input_path = args.input
    if not os.path.isfile(input_path):
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    if args.list_tracks:
        audio_tracks = get_audio_tracks(input_path)
        sub_tracks = get_subtitle_tracks(input_path)
        print("Audio tracks:")
        for i, t in enumerate(audio_tracks):
            lang = t.get("tags", {}).get("language", "?")
            title = t.get("tags", {}).get("title", "")
            codec = t.get("codec_name", "?")
            label = f"{title} " if title else ""
            print(f"  {i}: {label}[{lang}] ({codec})")
        print("\nSubtitle tracks:")
        for i, t in enumerate(sub_tracks):
            lang = t.get("tags", {}).get("language", "?")
            title = t.get("tags", {}).get("title", "")
            nf = t.get("tags", {}).get("NUMBER_OF_FRAMES", "?")
            label = f"{title} " if title else ""
            print(f"  {i} (stream {t['index']}): {label}[{lang}] ({nf} events)")
        return

    if args.output:
        output_path = args.output
    else:
        p = Path(input_path)
        output_path = str(p.with_stem(p.stem + "_tts"))

    print(f"Input:  {Path(input_path)}")
    print(f"Output: {output_path}")

    # -- Discover audio tracks --
    print("\n[1/4] Discovering tracks...")
    audio_tracks = get_audio_tracks(input_path)
    if not audio_tracks:
        print("Error: no audio tracks found in the video file.")
        sys.exit(1)

    audio_idx = args.audio if args.audio is not None else 0
    if audio_idx >= len(audio_tracks):
        print(f"Error: audio track {audio_idx} does not exist (file has {len(audio_tracks)} audio tracks).")
        sys.exit(1)

    a = audio_tracks[audio_idx]
    a_lang = a.get("tags", {}).get("language", "?")
    a_title = a.get("tags", {}).get("title", "")
    print(f"  Mixing TTS over audio track {audio_idx}: {a_title + ' ' if a_title else ''}[{a_lang}]")

    # -- Discover subtitles --
    all_tracks = get_subtitle_tracks(input_path)
    if not all_tracks:
        print("Error: no subtitle tracks found in the video file.")
        sys.exit(1)

    tracks = [t for t in all_tracks if t.get("codec_name") not in BITMAP_SUB_CODECS]
    if not tracks:
        print("Error: only bitmap (image-based) subtitle tracks found.")
        print("  TTS requires text-based subtitles (SRT, ASS, etc.).")
        print("  Use --list-tracks to see what's in the file.")
        sys.exit(1)

    if args.sub_index is not None:
        if args.sub_index >= len(tracks):
            print(f"Error: subtitle track {args.sub_index} does not exist (file has {len(tracks)} text subtitle tracks).")
            sys.exit(1)
        sub_index = tracks[args.sub_index]["index"]
    else:
        sub_index = pick_subtitle_track(tracks)

    print(f"  Using subtitle stream index: {sub_index}")

    duration_s = get_video_duration(input_path)
    duration_ms = int(duration_s * 1000)
    print(f"  Video duration: {duration_s:.1f}s ({duration_s / 60:.1f} min)")

    with tempfile.TemporaryDirectory(prefix="paparapa_") as tmpdir:
        # -- Extract subtitles --
        print("\n[2/4] Extracting subtitles...")
        sub_path = extract_subtitles(input_path, sub_index, tmpdir)
        events = parse_subtitles(sub_path)
        print(f"  Found {len(events)} subtitle lines.")

        # -- Generate TTS --
        print(f"\n[3/4] Generating TTS audio (voice={args.voice or 'default'}, rate={args.rate})...")
        sapi = create_sapi_voice(args.voice, args.rate)
        tts_wav_path = assemble_tts_track(events, sapi, duration_ms, tmpdir, args.volume)
        print(f"  TTS track: {os.path.getsize(tts_wav_path) / 1024 / 1024:.1f} MB")

        # -- Mux --
        print(f"\n[4/4] Muxing TTS track into output file...")
        mux_tts_track(input_path, tts_wav_path, output_path, tmpdir,
                      audio_idx, args.track_name)

    print(f"\nDone! Output written to: {output_path}")


if __name__ == "__main__":
    main()
