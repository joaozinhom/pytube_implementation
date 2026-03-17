from pytubefix import YouTube
if __name__ == "__main__":from pytubefix import YouTube

if __name__ == "__main__":
    with open('links.txt', 'r') as file:
        for link in file:
            link = link.strip()
            video = YouTube(link)
            audio_stream = video.streams.get_audio_only()
            audio_stream.download()
            print("✅ 😎 🎧")
