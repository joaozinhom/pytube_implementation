# pytube_implementation

A collection of Python scripts for downloading YouTube videos, audio-only streams, MP3s, and playlists — powered by [pytubefix](https://github.com/JuanBindez/pytubefix).

## Scripts

| File | What it does |
|---|---|
| `main.py` | Download a YouTube video at highest resolution |
| `audio.py` | Download audio-only stream from a video |
| `mp3.py` | Download and save as `.mp3` |
| `playlist.py` | dowload all audios listed in liks.txt |
| `playlist_of_yt.py` |Dowload all audios from a yt playlist link|

## Installation & Usage

Clone the repo, then use `uv` to install dependencies and run any script directly:

```bash
git clone https://github.com/joaozinhom/pytube_implementation.git
cd pytube_implementation

uv sync
```

That's it. Now run any script with:

```bash
uv run main.py
uv run audio.py
uv run mp3.py
uv run playlist.py
uv run playlist_of_yt.py
```

`uv sync` reads `pyproject.toml`, creates an isolated environment, and installs all dependencies automatically. No manual venv activation needed.

## Requirements

- [uv](https://docs.astral.sh/uv/) — install it with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Python 3.10+ (uv will manage this for you)

## License

MIT