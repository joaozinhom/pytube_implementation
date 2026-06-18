import yt_dlp
import subprocess
import os

def fix_m4a(filepath):
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

if __name__ == "__main__":
    link = input("Enter the link of the audio: ")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '%(title)s.%(ext)s',
        'quiet': False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=True)
        filepath = ydl.prepare_filename(info)

    fix_m4a(filepath)
    print("✅ 😎 🎧")