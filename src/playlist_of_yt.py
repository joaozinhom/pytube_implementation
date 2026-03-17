from pytubefix import Playlist, YouTube
from pytubefix.exceptions import AgeRestrictedError

if __name__ == "__main__":
    playlist_url = input("Enter the link of the playlist: ")
    playlist = Playlist(playlist_url) 
    
    for url in playlist.video_urls:
        try:
            video = YouTube(url)
            audio_stream = video.streams.get_audio_only()
            audio_stream.download()
            print("✅ 😎 🎧")
        except AgeRestrictedError:
            print(f"⚠️ Skipping age-restricted video: {url}")
            continue
        except Exception as e:
            print(f"❌ Error: {e}")
            continue