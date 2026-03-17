from pytubefix import YouTube
if __name__ == "__main__":
    link = input("Enter the link of the audio: ") 
    yt = YouTube(link)
    content = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
    content.download()
    print("✅ 😎 🎧")
