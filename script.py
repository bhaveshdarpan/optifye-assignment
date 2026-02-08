import requests
import os

API_KEY = "Q9JWrl1YeTCBRhnZcJfnTpr513U7ZWMf8pUPBud6jYzFAdOThycDfpBJ"
headers = {
    "Authorization": API_KEY
}

query = "city"
url = f"https://api.pexels.com/videos/search?query={query}&per_page=10"

resp = requests.get(url, headers=headers).json()

os.makedirs("videos", exist_ok=True)

for i, video in enumerate(resp["videos"]):
    video_url = video["video_files"][0]["link"]
    data = requests.get(video_url).content
    with open(f"videos/video_{i}.mp4", "wb") as f:
        f.write(data)

print("Downloaded videos")
