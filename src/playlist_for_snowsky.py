import yt_dlp
import subprocess
import os
import argparse
import requests
from mutagen.mp4 import MP4, MP4Cover


def fix_and_tag(filepath: str, track_number: int, total_tracks: int, album: str) -> None:
    base, ext = os.path.splitext(filepath)
    fixed = base + '_fixed.m4a'

    subprocess.run([
        'ffmpeg', '-i', filepath,
        '-vn', '-codec:a', 'copy',
        '-movflags', '+faststart',
        fixed
    ], check=True)

    os.remove(filepath)
    os.rename(fixed, filepath)

    audio = MP4(filepath)
    audio['trkn'] = [(track_number, total_tracks)]
    audio['\xa9alb'] = [album]
    audio.save()


def get_cover_itunes(title: str, artist: str | None) -> bytes | None:
    term = f"{artist} {title}" if artist else title
    try:
        r = requests.get(
            'https://itunes.apple.com/search',
            params={'term': term, 'media': 'music', 'limit': 1},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get('results', [])
        if not results:
            return None
        art_url = results[0].get('artworkUrl100', '').replace('100x100bb', '600x600bb')
        if not art_url:
            return None
        resp = requests.get(art_url, timeout=15)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except requests.RequestException as e:
        print(f"    [iTunes ERROR] {e}")
    return None


def embed_cover(filepath: str, image_bytes: bytes) -> None:
    fmt = MP4Cover.FORMAT_PNG if image_bytes[:8] == b'\x89PNG\r\n\x1a\n' else MP4Cover.FORMAT_JPEG
    audio = MP4(filepath)
    audio['covr'] = [MP4Cover(image_bytes, imageformat=fmt)]
    audio.save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", help="Playlist URL (optional, will prompt if not provided)")
    parser.add_argument("--albumcover", action="store_true", help="Use the same cover art for all tracks")
    args = parser.parse_args()

    playlist_url = args.url or input("Enter the link of the playlist: ")

    os.makedirs("downloaded", exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': 'downloaded/%(title)s.%(ext)s',
        'quiet': False,
        'ignoreerrors': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        entries = [e for e in info.get('entries', []) if e]
        total = len(entries)
        album_name = info.get('title', 'Unknown Album')
        print(f"Found {total} videos in: {album_name}")

        album_cover = None

        for i, entry in enumerate(entries, start=1):
            try:
                title  = entry.get('title', f'track_{i}')
                artist = entry.get('artist') or entry.get('uploader')

                info_single = ydl.extract_info(entry['webpage_url'], download=True)
                raw_path = ydl.prepare_filename(info_single)

                ext = os.path.splitext(raw_path)[1]
                safe_title = title.replace('/', '-').replace('\x00', '')
                indexed_path = f"downloaded/{i:02d} - {safe_title}{ext}"
                if raw_path != indexed_path:
                    os.rename(raw_path, indexed_path)
                filepath = indexed_path

                fix_and_tag(filepath, track_number=i, total_tracks=total, album=album_name)

                if args.albumcover:
                    if album_cover is None:
                        album_cover = get_cover_itunes(title, artist)
                        if album_cover:
                            print(f"    [cover] album cover fetched from first track")
                        else:
                            print(f"    [cover] album cover not found")
                    cover = album_cover
                else:
                    cover = get_cover_itunes(title, artist)

                if cover:
                    embed_cover(filepath, cover)
                    print(f"    [cover] embedded")
                else:
                    print(f"    [cover] not found")

                print(f"✅ [{i}/{total}] {title}")

            except Exception as e:
                print(f"❌ [{i}/{total}] Error: {e}")
                continue