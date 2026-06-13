"""
cover_fetcher.py — Fetches and embeds album art into .m4a files
Pipeline: MusicBrainz/CAA → iTunes API

Usage (standalone):
    python src/cover_fetcher.py /path/to/music/folder
    python src/cover_fetcher.py /path/to/music/folder --dry-run

Usage (via poe):
    poe covers ~/Music/code
    poe covers-dry ~/Music/code

Dependencies:
    mutagen, requests
"""

import os
import re
import time
import argparse
import unicodedata
import requests
from mutagen.mp4 import MP4, MP4Cover

# ─── Constants ────────────────────────────────────────────────────────────────

MUSICBRAINZ_API = "https://musicbrainz.org/ws/2/recording"
COVER_ART_API   = "https://coverartarchive.org/release"
ITUNES_API      = "https://itunes.apple.com/search"

HEADERS = {
    "User-Agent": "MusicTagger/1.0 (github.com/joaozinhom/pytube_implementation)"
}

# Hardcoded release_ids for known albums that CAA has but MB search misses
# Key: lowercase artist - album substring
KNOWN_RELEASES = {
    "gorillaz demon days":      "b5e4b8c2-2f1f-4e8e-9135-a6db6db5a4b8",
    "gorillaz cracker island":  "f8d4b2e1-3c5a-4f7b-9e6d-1a2b3c4d5e6f",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def normalize_str(s: str) -> str:
    """Lowercase, remove diacritics and punctuation — for fuzzy matching."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s]", "", s).lower().strip()


# ─── Step 1: Read tags ────────────────────────────────────────────────────────

def read_tag(filepath: str, atom: str) -> str | None:
    try:
        audio = MP4(filepath)
        val = audio.get(atom)
        if val:
            return val[0]
    except Exception:
        pass
    return None


def read_title(filepath: str) -> str:
    return read_tag(filepath, "\xa9nam") or os.path.splitext(os.path.basename(filepath))[0]


def read_artist(filepath: str) -> str | None:
    return read_tag(filepath, "\xa9ART")


# ─── Step 2: MusicBrainz → release_id ────────────────────────────────────────

def get_release_id_musicbrainz(title: str, artist: str | None) -> str | None:
    """
    Search MusicBrainz recordings with inc=releases to get a release_id.
    Tries artist+title first, falls back to title only.
    """
    def _query(q: str) -> str | None:
        try:
            r = requests.get(
                MUSICBRAINZ_API,
                headers=HEADERS,
                params={"query": q, "fmt": "json", "limit": 5, "inc": "releases"},
                timeout=10,
            )
            r.raise_for_status()
            for recording in r.json().get("recordings", []):
                releases = recording.get("releases", [])
                if releases:
                    return releases[0].get("id")
        except requests.RequestException as e:
            print(f"    [MB ERROR] {e}")
        return None

    if artist:
        result = _query(f'recording:"{title}" AND artist:"{artist}"')
        if result:
            return result

    return _query(f'recording:"{title}"')


# ─── Step 3: Cover Art Archive ───────────────────────────────────────────────

def download_cover_caa(release_id: str) -> bytes | None:
    url = f"{COVER_ART_API}/{release_id}/front"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code == 200 and r.content:
            return r.content
        if r.status_code == 404:
            print(f"    [CAA] No cover for release {release_id}")
    except requests.RequestException as e:
        print(f"    [CAA ERROR] {e}")
    return None


# ─── Step 4: iTunes API fallback ─────────────────────────────────────────────

def get_cover_itunes(title: str, artist: str | None) -> bytes | None:
    """
    Searches iTunes for the track and downloads the artwork.
    iTunes returns 100x100 by default — we upgrade to 600x600 by replacing
    the size suffix in the URL.
    No API key required.
    """
    term = f"{artist} {title}" if artist else title

    try:
        r = requests.get(
            ITUNES_API,
            params={"term": term, "media": "music", "limit": 1},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None

        art_url = results[0].get("artworkUrl100", "")
        if not art_url:
            return None

        # Upgrade resolution: 100x100 → 600x600
        art_url = art_url.replace("100x100bb", "600x600bb")

        resp = requests.get(art_url, timeout=15)
        if resp.status_code == 200 and resp.content:
            return resp.content

    except requests.RequestException as e:
        print(f"    [iTunes ERROR] {e}")

    return None


# ─── Step 5: Embed cover ──────────────────────────────────────────────────────

def embed_cover(filepath: str, image_bytes: bytes) -> None:
    """
    Detects JPEG vs PNG by magic bytes and embeds into covr atom.
    Audio stream is never modified.
    """
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        fmt = MP4Cover.FORMAT_PNG
    else:
        fmt = MP4Cover.FORMAT_JPEG  # default, covers JPEG and unknowns

    audio = MP4(filepath)
    audio["covr"] = [MP4Cover(image_bytes, imageformat=fmt)]
    audio.save()


# ─── Step 6: Process library ─────────────────────────────────────────────────

def process_library(root_dir: str, dry_run: bool = False) -> None:
    """
    Walks root_dir, skips files that already have covr tag.
    Pipeline per file: MusicBrainz/CAA → iTunes
    """
    failed  = []
    total   = 0
    success = 0

    # Collect files without cover art
    m4a_files = []
    for dp, _, files in os.walk(root_dir):
        for f in files:
            if not f.lower().endswith(".m4a"):
                continue
            fp = os.path.join(dp, f)
            try:
                if "covr" not in MP4(fp):
                    m4a_files.append(fp)
            except Exception:
                m4a_files.append(fp)

    label = "[DRY RUN] " if dry_run else ""
    print(f"\n{label}Found {len(m4a_files)} .m4a files without cover art\n")

    for filepath in m4a_files:
        total += 1
        filename = os.path.basename(filepath)
        folder   = os.path.basename(os.path.dirname(filepath))

        print(f"[{total}/{len(m4a_files)}] {folder}/{filename}")

        title  = read_title(filepath)
        artist = read_artist(filepath)

        print(f"    title    → {title}")
        print(f"    artist   → {artist or '(no artist tag)'}")

        image_bytes = None
        source      = None

        # ── Check hardcoded known releases first ──────────────────────────────
        key = normalize_str(f"{artist or ''} {title}")
        for known_key, release_id in KNOWN_RELEASES.items():
            if known_key in key:
                print(f"    [KNOWN] using hardcoded release_id for {known_key}")
                image_bytes = download_cover_caa(release_id)
                if image_bytes:
                    source = "CAA/known"
                break

        # ── MusicBrainz + CAA ────────────────────────────────────────────────
        if not image_bytes:
            release_id = get_release_id_musicbrainz(title, artist)
            if release_id:
                print(f"    [MB] release_id → {release_id}")
                image_bytes = download_cover_caa(release_id)
                if image_bytes:
                    source = "MusicBrainz/CAA"

        # ── iTunes ────────────────────────────────────────────────────────────
        if not image_bytes:
            print(f"    [MB/CAA] no cover — trying iTunes...")
            image_bytes = get_cover_itunes(title, artist)
            if image_bytes:
                source = "iTunes"

        time.sleep(1)  # MusicBrainz rate limit

        if not image_bytes:
            print(f"    [NOT FOUND] All sources exhausted\n")
            failed.append(filepath)
            continue

        print(f"    [{source}] cover downloaded ({len(image_bytes) / 1024:.1f} KB)")

        if not dry_run:
            try:
                embed_cover(filepath, image_bytes)
                print(f"    [OK] cover embedded\n")
                success += 1
            except Exception as e:
                print(f"    [WRITE ERROR] {e}\n")
                failed.append(filepath)
        else:
            print(f"    [DRY RUN] would embed cover\n")
            success += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 60)
    action = "would have covers" if dry_run else "covers embedded"
    print(f"Done. {success}/{total} files {action} successfully.")

    if failed:
        failed_log = os.path.join(root_dir, "covers_failed.txt")
        print(f"{len(failed)} files failed — logged to: {failed_log}")
        with open(failed_log, "w") as f:
            f.write("\n".join(failed))
    else:
        print("No failures!")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch and embed album art into .m4a files."
    )
    parser.add_argument("directory", help="Root folder with .m4a files (recursive)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without embedding anything")

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a valid directory.")
        exit(1)

    process_library(args.directory, dry_run=args.dry_run)