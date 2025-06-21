import yt_dlp

def get_video_title(url):
    ydl_opts = {"quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("title", "Título no encontrado")

video_url = "https://youtu.be/PWBRArka4dQ?si=kTq7jaVaxvtWCJbc"
titulo = get_video_title(video_url)
print(f"Título del video: {titulo}")
