from pytubefix import YouTube
if __name__ == "__main__":
    link = input("Enter the link of the video: ")
    video = YouTube(link)
    stream = video.streams.get_highest_resolution()
    stream.download()
    print("✅ 😎 🎧")
