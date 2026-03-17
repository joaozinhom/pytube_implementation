# pytube_implementation

A collection of Python scripts for downloading YouTube videos, audio-only streams, MP3s, and playlists — powered by [pytubefix](https://github.com/JuanBindez/pytubefix).

## Scripts

| File | What it does |
|---|---|
| `main.py` | Download a YouTube video at highest resolution |
| `audio.py` | Download audio-only stream from a video |
| `mp3.py` | Download and save as `.mp3` |
| `playlist.py` | Download all audios listed in `links.txt` |
| `playlist_of_yt.py` | Download all audios from a YouTube playlist link |

## Installation & Usage

Clone the repo, then use `uv` to install dependencies and run any script directly:

```bash
git clone https://github.com/joaozinhom/pytube_implementation.git
cd pytube_implementation

uv sync
```
Then run any task with `uv  run poe <task>` (or `poe <task>`):

```bash
uv run poe  main            # runs python src/main.py — Download a YouTube video at highest resolution
uv run poe audio           # runs python src/audio.py — Download audio-only stream from a video
uv run poe mp3             # runs python src/mp3.py — Download and save as .mp3
uv run poe playlist        # runs python src/playlist.py — Download all audios listed in links.txt
uv run poe  playlist_of_yt  # runs python src/playlist_of_yt.py — Download all audios from a YouTube playlist link
```

These tasks are defined in `pyproject.toml` under `[tool.poe.tasks]` and point to the scripts in `src/`.

## Requirements

- [uv](https://docs.astral.sh/uv/)