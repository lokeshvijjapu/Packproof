import os
import time
import json
import requests

VIDEO_PATH = "/home/neonflake/packproof/videos"
IMAGE_PATH = "/home/neonflake/packproof/images"
LOG_FILE   = "/home/neonflake/packproof/upload_log.json"

API_URL = "https://visitwise.claricall.space/api/videos/add"
WAKE_URL = "https://visitwise.claricall.space"

WAKEUP_TIMEOUT = 15
UPLOAD_TIMEOUT = 600   # 10 minutes

def load_queue():
    if not os.path.exists(LOG_FILE):
        return {"pending": [], "uploaded": []}
    with open(LOG_FILE, "r") as f:
        return json.load(f)

def save_queue(data):
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def wake_up_server():
    try:
        print("âš¡ Waking server...")
        requests.get(WAKE_URL, timeout=WAKEUP_TIMEOUT)
        print("âœ… Server awake")
    except:
        print("âš  Server wake-up slow, continuing...")

def upload_entry(entry):
    invoice_id = entry["id"]

    video = f"{VIDEO_PATH}/{invoice_id}.mp4"
    image = f"{IMAGE_PATH}/{invoice_id}.jpg"

    if not os.path.exists(video):
        print(f"âš  Video file missing for {invoice_id}, retry later")
        return False

    print(f"ðŸ“¤ Uploading {invoice_id} ...")

    try:
        files = {
            "name": (None, invoice_id),
            "videoFile": ("video.mp4", open(video, "rb"), "video/mp4"),
        }
        if os.path.exists(image):
            files["imageFile"] = ("image.jpg", open(image, "rb"), "image/jpeg")

        response = requests.post(
            API_URL,
            files=files,
            timeout=UPLOAD_TIMEOUT
        )

        # Close file handles (avoid resource warning if only video)
        for v in files.values():
            if hasattr(v[1], 'close'):
                v[1].close()

        print("âœ… Status:", response.status_code)
        print("âœ… Response:", response.text)

        # âœ… Success if 200 or 201
        if response.status_code in [200, 201]:
            return True

        return False

    except requests.exceptions.Timeout:
        print("âŒ ERROR: Upload timed out (cold start or slow server)")
        return False

    except Exception as e:
        print("âŒ Upload error:", e)
        return False

def main():
    while True:
        queue = load_queue()

        if not queue["pending"]:
            print("â¸ No pending uploads. Waiting...")
            time.sleep(5)
            continue

        wake_up_server()

        new_pending = []

        for entry in queue["pending"]:
            if upload_entry(entry):
                # âœ… Move to uploaded list
                queue["uploaded"].append(entry)

                # âœ… DELETE FILES
                video = f"{VIDEO_PATH}/{entry['id']}.mp4"
                image = f"{IMAGE_PATH}/{entry['id']}.jpg"

                try:
                    if os.path.exists(video):
                        os.remove(video)
                    if os.path.exists(image):
                        os.remove(image)
                    print(f"ðŸ—‘ï¸ Deleted files for {entry['id']}")
                except Exception as e:
                    print(f"âš ï¸ Error deleting files for {entry['id']}: {e}")

            else:
                # keep pending for retry
                new_pending.append(entry)

        queue["pending"] = new_pending
        save_queue(queue)

        print("â¸ Waiting...\n")
        time.sleep(5)

if __name__ == "__main__":
    main()
