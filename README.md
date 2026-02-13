# paparapa_tts

A tool that reads the subtitles in a video file out loud using text-to-speech and saves a new copy of the video with the spoken subtitles mixed into the audio. Built for visually impaired users who can't read on-screen subtitles.

## What it does

Given a video file (like an `.mkv`) with embedded subtitles, paparapa_tts will:

1. Find the subtitle track in the video
2. Convert every subtitle line to speech, timed to match when it appears on screen
3. Save a new video file with **three audio tracks**:
   - **Track 1** - The original audio (unchanged)
   - **Track 2** - The original audio with TTS mixed in (so you hear both at once)
   - **Track 3** - TTS voice only (no background audio)

You can then switch between tracks in your video player (most players let you pick an audio track from a menu).

## Requirements

- **Windows 10 or 11**
- **Python 3.10 or newer** - [Download here](https://www.python.org/downloads/)
- **ffmpeg** - The setup script can install this for you automatically

## Setup

1. Download or clone this repository to a folder on your computer
2. Double-click **`setup.bat`**
3. A window will appear and walk through 4 checks. Wait for it to finish
4. If it says **"Setup complete"**, you're ready to go. Press any key to close the window

If it reports a problem, follow the instructions on screen, then run `setup.bat` again. It's safe to run as many times as needed.

> **Note:** When installing Python, make sure to check **"Add Python to PATH"** on the first screen of the installer. If you missed that step, the setup script will still try to find Python automatically.

## Usage

Open a Command Prompt, navigate to the project folder, and run:

```
.venv\Scripts\python.exe paparapa_tts.py "path\to\your\video.mkv"
```

The tool will process the video and save a new file with `_tts` added to the name (e.g. `video_tts.mkv`).

### Examples

**Basic usage** - process a video with default settings:
```
.venv\Scripts\python.exe paparapa_tts.py "D:\Anime\My Movie.mkv"
```

**Choose a different voice:**
```
.venv\Scripts\python.exe paparapa_tts.py "D:\Anime\My Movie.mkv" -v Zira
```

**Speed up the speech** (default is 175 words per minute):
```
.venv\Scripts\python.exe paparapa_tts.py "D:\Anime\My Movie.mkv" -r 210
```

**Slow down the speech:**
```
.venv\Scripts\python.exe paparapa_tts.py "D:\Anime\My Movie.mkv" -r 130
```

**Save to a specific output file:**
```
.venv\Scripts\python.exe paparapa_tts.py "D:\Anime\My Movie.mkv" -o "D:\Output\My Movie with TTS.mkv"
```

**Combine multiple options** (Zira voice, faster speech, custom output):
```
.venv\Scripts\python.exe paparapa_tts.py "D:\Anime\My Movie.mkv" -v Zira -r 200 -o "output.mkv"
```

**See what voices are available on your PC:**
```
.venv\Scripts\python.exe paparapa_tts.py --list-voices
```

**See what audio and subtitle tracks are in a video:**
```
.venv\Scripts\python.exe paparapa_tts.py "D:\Anime\My Movie.mkv" --list-tracks
```

**Pick a specific audio track to mix TTS over** (useful if the video has multiple audio tracks, like Japanese and English):
```
.venv\Scripts\python.exe paparapa_tts.py "D:\Anime\My Movie.mkv" -a 1
```

## All Options

| Option | Description | Default |
|---|---|---|
| `-v` / `--voice` | TTS voice name (e.g. `David`, `Zira`) | System default |
| `-r` / `--rate` | Speech speed in words per minute | `175` |
| `-o` / `--output` | Output file path | `<input>_tts.mkv` |
| `-a` / `--audio` | Which audio track to mix TTS over (0-based) | `0` (first track) |
| `-s` / `--sub-index` | Which subtitle track to use (by stream index) | Auto-picks the largest track |
| `--track-name` | Label for the new audio tracks in the output | `English (TTS)` |
| `--list-voices` | Show available TTS voices and exit | |
| `--list-tracks` | Show audio and subtitle tracks in the video and exit | |

## Troubleshooting

**"Python is not installed or not on PATH"**
Python is installed but Windows can't find it. Reinstall Python from [python.org](https://www.python.org/downloads/) and check the **"Add Python to PATH"** box during installation. Then run `setup.bat` again.

**"No subtitle tracks found"**
The video file doesn't have subtitles embedded in it. paparapa_tts only works with subtitles that are built into the video file (not separate `.srt` files).

**"No audio tracks found"**
The input file doesn't contain any audio. Make sure you're pointing at the correct video file.

**The speech is too fast / too slow**
Adjust the `-r` option. Lower numbers are slower, higher numbers are faster. `175` is the default. Try values between `120` (slow) and `250` (fast).

**Processing takes a long time**
This is normal. The tool generates a separate audio clip for every subtitle line, which can be thousands of clips for a full episode. A 25-minute video may take several minutes to process.

## License

Open source. See [LICENSE](LICENSE) for details.
