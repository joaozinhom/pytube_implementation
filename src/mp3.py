from pytubefix import YouTube
from moviepy import AudioFileClip
import os

if __name__ == "__main__":
    link = input("Enter the link of the audio: ") 
    yt = YouTube(link)
    content = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
    downloaded_file = content.download()
    
    base, ext = os.path.splitext(downloaded_file)
    mp3_file = base + '.mp3'
    
    audio_clip = AudioFileClip(downloaded_file)
    audio_clip.write_audiofile(mp3_file)
    audio_clip.close()
    
    os.remove(downloaded_file)
    
    print("✅ 😎 🎧")