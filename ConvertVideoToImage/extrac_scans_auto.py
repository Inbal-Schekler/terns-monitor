import requests
from requests.auth import HTTPDigestAuth
import os
from datetime import datetime, timedelta
import subprocess
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Authentication credentials
username = "atlit"
password = "atlit121271"

# Path to FFmpeg executable
ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"

# Camera configurations.
# days_to_download matches how long the server retains footage per camera.
# Both cameras output HEVC â€” transcoded to H.264 so files play without extra codecs.
# The "already exists" check makes this safe to run daily â€” skips already-downloaded files.
cameras = [
#cameras = [cam for cam in[
    {
        "name": "191",  # North camera (port 9090, H.264 from NVR) â€” server stores ~1 day
        "camera_id": "12e18ec2-2fa2-0985-ca44-e5b772c8909c",
        "duration": 2280,
        "base_folder": r"F:\My Drive\tern_project\terns_movies",
        "days_to_download": 1,
        "times_to_download": ["09:59:50", "14:59:50"]
    },
    {
        "name": "181",  # South camera (port 8080, HEVC from NVR) â€” server stores ~7 days
        "camera_id": "3ae02e93-9fb2-9d94-d1d7-5f23a05dc19b",
        "duration": 1990,
        "base_folder": r"F:\My Drive\tern_project\terns_movies",
        "days_to_download": 7,
        "times_to_download": ["10:01:30", "15:01:30"]
    }
]
#] if cam["name"] == "181"]

# Server details
server_ip = "212.179.113.90"
port = "7001"

# Process each camera
for cam in cameras:
    for day_offset in range(1, cam["days_to_download"] + 1):
        target_date = datetime.now() - timedelta(days=day_offset)
        year = target_date.strftime("%Y")
        save_folder = os.path.join(cam["base_folder"], year, cam["name"])
        os.makedirs(save_folder, exist_ok=True)

        date_str = target_date.strftime("%Y_%m_%d")

        for time_str in cam["times_to_download"]:
            time_parts = time_str.replace(":", "_")
            formatted_datetime = f"{date_str}_{time_parts}"
            final_file = f"atlitcam{cam['name']}.stream_{formatted_datetime}.mkv"
            final_path = os.path.join(save_folder, final_file)

            # Skip download if file already exists
            if os.path.exists(final_path):
                print(f"Skipping: {final_path} already exists.")
                continue

            start_time = f"{target_date.strftime('%Y-%m-%d')}T{time_str}"
            url = f"https://{server_ip}:{port}/media/{cam['camera_id']}.mkv?pos={start_time}&duration={cam['duration']}"

            print(f"\nDownloading camera {cam['name']} at {start_time}...")

            temp_file = os.path.join(save_folder, "temp_unseekable.mkv")
            try:
                response = requests.get(url, auth=HTTPDigestAuth(username, password),
                                        stream=True, verify=False)
                if response.status_code != 200:
                    print(f"Failed to download. Status code: {response.status_code}")
                    print("Response:", response.text[:200])
                    continue

                with open(temp_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"Downloaded temp file.")

            except Exception as e:
                print(f"Download error: {e}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                continue

            # Both cameras deliver HEVC from the NVR â€” transcode to H.264 for universal playback.
            # North camera (191) already arrives as H.264 from this NVR, so copy is enough for it.
            print("Fixing video (making it seekable)...")
            if cam["name"] == "181":
                ffmpeg_command = [ffmpeg_path, "-loglevel", "error",
                                  "-i", temp_file,
                                  "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                                  "-c:a", "copy", final_path]
            else:
                ffmpeg_command = [ffmpeg_path, "-loglevel", "error",
                                  "-i", temp_file, "-c", "copy", final_path]

            try:
                subprocess.run(ffmpeg_command, check=True)
                print(f"Saved: {final_path}")
                os.remove(temp_file)
            except subprocess.CalledProcessError as e:
                print(f"FFmpeg error: {e}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
