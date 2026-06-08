"""
tagger.py — Music metadata tagger for .m4a files
Reads filename, queries MusicBrainz API, falls back to Last.fm.
Writes title and artist tags.

Usage (standalone):
    python src/tagger.py /path/to/music/folder
    python src/tagger.py /path/to/music/folder --retag-failed

Usage (via poe):
    poe tagger ~/Music/code
    poe tagger-failed ~/Music/code   # only retag files with no title tag

Dependencies:
    mutagen, requests
"""

import os
import re
import time
import argparse
import requests
from mutagen.mp4 import MP4

# ─── Constants ────────────────────────────────────────────────────────────────

MUSICBRAINZ_API = "https://musicbrainz.org/ws/2/recording"
LASTFM_API      = "https://ws.audioscrobbler.com/2.0/"
LASTFM_API_KEY  = "6b1be31a913a275ee57a7906b93cc98c"

HEADERS = {
    "User-Agent": "MusicTagger/1.0 (github.com/joaozinhom/pytube_implementation)"
}

# Known artists for inverted filename detection ("Title - Artist")
KNOWN_ARTISTS = {
    "linkin park", "gorillaz", "daft punk", "arctic monkeys",
    "fred again", "fred again..", "metro boomin", "juice wrld",
    "post malone", "eminem", "imagine dragons", "twenty one pilots",
    "the killers", "dominic fike", "jorja smith", "stromae",
    "childish gambino", "akon", "bob sinclar", "woodkid",
    "travis emmons", "remi wolf", "charlie puth", "jack stauber",
    "pusha t", "denzel curry", "sigala", "breakbot", "minuit machine",
    "jay-z", "jayz",
}

NOISE_PATTERNS = [
    # Official variants
    r"\(?official\s*(music\s*)?(audio|video|hd\s*video|lyric\s*video|lyrics|clip|visualizer)\)?",
    r"\[official\s*(music\s*)?(audio|video|hd\s*video|lyric\s*video|lyrics|clip|visualizer)\]",
    r"\(official\)",  r"\[official\]",
    # Lyrics / quality
    r"\(lyrics?\)",   r"\[lyrics?\]",
    r"\(high\s*quality\)", r"\[high\s*quality\]",
    r"\(hq\)",  r"\[hq\]",
    r"\(hd\)",  r"\[hd\]",
    r"\(audio\)", r"\[audio\]",
    r"\(visuali[sz]er\)", r"\[visuali[sz]er\]",
    r"\(explicit\)", r"\[explicit\]",
    r"\(live[^)]*\)", r"\[live[^\]]*\]",
    r"\(remastered[^)]*\)", r"\[remastered[^\]]*\]",
    r"\(\d{4}\s*remaster\w*\)", r"\[\d{4}\s*remaster\w*\]",
    r"remastered",
    # Release / label
    r"\[monstercat\s*release\]",
    r"\[glasgow\s*underground\]",
    r"\[out\s*now\]",
    r"\(radio\s*edit\)",
    r"\(extended\s*mix\)",
    r"\(album\s*version[^)]*\)",
    # Soundtrack / collab context
    r"\(from\s+[^)]+\)",
    r"\[from\s+[^\]]+\]",
    r"\|\s*arcane[^|]*",
    r"\|\s*league\s*of\s*legends[^|]*",
    r"\|\s*riot\s*games[^|]*",
    r"\|\s*vevo[^|]*",
    r"\|\s*beatbox[^|]*",
    r"\|\s*music\s*video[^|]*",
    r"spider[- ]?man[^-\n]*",
    r"arcane\s*(season\s*\d+)?",
    r"league\s*of\s*legends",
    r"riot\s*games\s*music",
    r"cyberpunk\s*\d*\s*soundtrack\s*-?\s*",
    r"by\s+rosa\s+walton[^)]*",
    # Remix / version (keep title, strip label)
    r"\([^)]*official\s*remix[^)]*\)",
    r"\[[^\]]*official\s*remix[^\]]*\]",
    r"\([^)]*extended\s*mix[^)]*\)",
    # feat stripping
    r"ft\.?\s+[^(\[|\n\-]+",
    r"feat\.?\s+[^(\[|\n\-]+",
    # Misc
    r"[☝️]+",
    r"no\.\s*\d+",
    r"\(copyright\s*free\)",
    r"\[copyright\s*free\]",
    r"4k\s*upgrade",
    r"\*",
    r"\|.*$",           # anything after a pipe
    r"#\w+",            # hashtags
]


# ─── Step 1: Normalize separators ────────────────────────────────────────────

def normalize(filename: str) -> str:
    """
    Normalize unicode separators and decorative characters before any parsing.

    Fixes:
    - Em dash / en dash → regular hyphen  (DAFT PUNK – AROUND THE WORLD)
    - Decorative unicode letters → plain   (G̲o̲rillaz)
    - Curly quotes → removed               (Regina Spektor - "Don't Leave Me")
    - Double spaces → single
    """
    # Em dash (—), en dash (–), figure dash (‒), horizontal bar (―) → " - "
    name = re.sub(r'\s*[–—‒―]\s*', ' - ', filename)

    # Remove decorative combining unicode (underline/overline diacritics etc.)
    # This fixes "G̲o̲rillaz" → "Gorillaz"
    import unicodedata
    name = ''.join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'  # Mn = non-spacing mark
    )

    # Remove curly quotes and straight quotes
    name = name.replace('"', '').replace('\u201c', '').replace('\u201d', '')
    name = name.replace("'", "'")  # normalize curly apostrophe

    # Collapse double spaces
    name = re.sub(r'\s{2,}', ' ', name).strip()

    return name


# ─── Step 2: Clean filename ───────────────────────────────────────────────────

def clean_filename(filename: str) -> str:
    """
    Remove .m4a extension, normalize, then strip all noise patterns.
    """
    name = os.path.splitext(filename)[0]
    name = normalize(name)

    for pattern in NOISE_PATTERNS:
        name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)

    name = re.sub(r'\s{2,}', ' ', name).strip().strip('-').strip()
    return name


# ─── Step 3: Parse artist and title ──────────────────────────────────────────

def parse_artist_title(cleaned: str) -> tuple[str | None, str]:
    """
    Detects "Artist - Title" or inverted "Title - Artist".
    Falls back to (None, cleaned) if no separator found.
    """
    if ' - ' not in cleaned:
        return None, cleaned.strip()

    left, right = cleaned.split(' - ', maxsplit=1)
    left  = left.strip()
    right = right.strip()

    # Inverted detection: right token is a known artist
    if right.lower() in KNOWN_ARTISTS:
        return right, left

    return left, right


# ─── Step 4a: MusicBrainz ────────────────────────────────────────────────────

def search_musicbrainz(artist: str | None, title: str) -> str | None:
    query = (
        f'recording:"{title}" AND artist:"{artist}"'
        if artist else
        f'recording:"{title}"'
    )
    try:
        r = requests.get(
            MUSICBRAINZ_API,
            headers=HEADERS,
            params={"query": query, "fmt": "json", "limit": 1},
            timeout=10,
        )
        r.raise_for_status()
        recordings = r.json().get("recordings", [])
        if recordings:
            return recordings[0].get("title")
    except requests.RequestException as e:
        print(f"    [MB ERROR] {e}")
    return None


# ─── Step 4b: Last.fm fallback ───────────────────────────────────────────────

def search_lastfm(artist: str | None, title: str) -> tuple[str | None, str | None]:
    """
    Returns (canonical_title, canonical_artist) or (None, None).
    """
    params = {
        "method":      "track.search",
        "track":       title,
        "api_key":     LASTFM_API_KEY,
        "format":      "json",
        "limit":       1,
        "autocorrect": 1,
    }
    if artist:
        params["artist"] = artist

    try:
        r = requests.get(LASTFM_API, params=params, timeout=10)
        r.raise_for_status()
        matches = (
            r.json()
             .get("results", {})
             .get("trackmatches", {})
             .get("track", [])
        )
        if matches:
            return matches[0].get("name"), matches[0].get("artist")
    except requests.RequestException as e:
        print(f"    [LFM ERROR] {e}")
    return None, None


# ─── Step 5: Write tags ───────────────────────────────────────────────────────

def write_tags(filepath: str, title: str, artist: str | None) -> None:
    """
    Writes ©nam (title) and optionally ©ART (artist) to the .m4a.
    Audio stream is never modified.
    """
    audio = MP4(filepath)
    audio["\xa9nam"] = [title]
    if artist:
        audio["\xa9ART"] = [artist]
    audio.save()


# ─── Step 6: Process library ─────────────────────────────────────────────────

def process_library(root_dir: str, only_untagged: bool = False) -> None:
    """
    Walks root_dir recursively and tags .m4a files.
    If only_untagged=True, skips files that already have a ©nam tag.
    Writes title + artist. Logs failures to failed.txt.
    """
    failed  = []
    total   = 0
    success = 0

    m4a_files = []
    for dp, _, files in os.walk(root_dir):
        for f in files:
            if not f.lower().endswith(".m4a"):
                continue
            fp = os.path.join(dp, f)
            if only_untagged:
                try:
                    audio = MP4(fp)
                    if "\xa9nam" in audio:
                        continue  # already tagged, skip
                except Exception:
                    pass
            m4a_files.append(fp)

    mode = "untagged files only" if only_untagged else "all files"
    print(f"\nFound {len(m4a_files)} .m4a files ({mode}) under: {root_dir}\n")

    for filepath in m4a_files:
        total += 1
        filename = os.path.basename(filepath)
        folder   = os.path.basename(os.path.dirname(filepath))

        print(f"[{total}/{len(m4a_files)}] {folder}/{filename}")

        cleaned = clean_filename(filename)
        print(f"    cleaned  → {cleaned}")

        artist, title = parse_artist_title(cleaned)
        print(f"    artist   → {artist or '(not in filename)'}")
        print(f"    title    → {title}")

        # MusicBrainz
        canonical_title  = search_musicbrainz(artist, title)
        canonical_artist = artist  # MB doesn't return artist in basic query

        if canonical_title:
            source = "MB"
        else:
            print(f"    [MB] not found — trying Last.fm...")
            canonical_title, lfm_artist = search_lastfm(artist, title)
            if canonical_title:
                source = "LFM"
                # Use Last.fm artist if we didn't have one from filename
                if not canonical_artist and lfm_artist:
                    canonical_artist = lfm_artist
            else:
                source = None

        time.sleep(1)  # MusicBrainz rate limit

        if not canonical_title:
            print(f"    [NOT FOUND] Neither MB nor Last.fm matched\n")
            failed.append(filepath)
            continue

        print(f"    [{source}] title  → {canonical_title}")
        print(f"    [{source}] artist → {canonical_artist or '(none)'}")

        try:
            write_tags(filepath, canonical_title, canonical_artist)
            print(f"    [OK] tags written\n")
            success += 1
        except Exception as e:
            print(f"    [WRITE ERROR] {e}\n")
            failed.append(filepath)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print(f"Done. {success}/{total} files tagged successfully.")

    if failed:
        failed_log = os.path.join(root_dir, "failed.txt")
        print(f"{len(failed)} files failed — logged to: {failed_log}")
        with open(failed_log, "w") as f:
            f.write("\n".join(failed))
    else:
        print("No failures!")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag .m4a files with title + artist from MusicBrainz/Last.fm."
    )
    parser.add_argument("directory", help="Root folder with .m4a files (recursive)")
    parser.add_argument(
        "--retag-failed",
        action="store_true",
        help="Only process files that have no title tag yet"
    )

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a valid directory.")
        exit(1)

    process_library(args.directory, only_untagged=args.retag_failed)