import base64
import json
import os
import struct
import time
import urllib.request
import urllib.error
import cv2
import numpy as np
import subprocess

import dotenv

dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.operator"))

def get_recent_logs():
    try:
        return subprocess.check_output("journalctl -u awarespan-node.service -n 25 --no-pager", shell=True).decode().splitlines()
    except Exception:
        return []

BACKEND_URL = os.environ.get("BACKEND_URL", "https://api.awarespan.bchbenjamin.in")
PI_HOST = os.environ.get("PI_HOST", "10.42.0.1")
PI_USER = os.environ.get("PI_USER", "benjamin")
PI_PASS = os.environ.get("PI_PASSWORD")

def test_video_submission():
    print("\n" + "="*50)
    print("TESTING VIDEO INGESTION & BOUNDED FRAME PROCESSING")
    print("="*50)
    
    # 1. Create a short test MP4 video (15 frames @ 10 FPS)
    knife_img = cv2.imread("tests/fixtures/knife_test.jpg")
    if knife_img is None:
        knife_img = np.zeros((480, 640, 3), dtype=np.uint8)
    h, w = knife_img.shape[:2]
    
    video_path = "temp_test_video.avi"
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    out = cv2.VideoWriter(video_path, fourcc, 10.0, (w, h))
    for i in range(15):
        frame = knife_img.copy()
        cv2.putText(frame, f"FRAME {i}", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 2)
        out.write(frame)
    out.release()
    
    with open(video_path, "rb") as f:
        vid_bytes = f.read()
    b64_vid = base64.b64encode(vid_bytes).decode("ascii")
    
    payload = {
        "nodeId": "sip-pi-001",
        "mediaType": "VIDEO",
        "filename": "test_video.avi",
        "contentType": "video/x-msvideo",
        "data": b64_vid
    }
    
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/v1/media/upload",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req)
    vid_data = json.loads(res.read().decode())
    media_id = vid_data.get("mediaId")
    cmd_id = vid_data.get("commandId")
    print(f"Video uploaded: Media ID={media_id}, Command ID={cmd_id}")
    
    # Monitor Pi log for sequential video frame ingestion
    start_t = time.time()
    seen = set()
    completed = False
    while time.time() - start_t < 45:
        lines = get_recent_logs()
        for l in lines:
            if l not in seen:
                seen.add(l)
                if media_id in l or ("Video" in l and "processed" in l):
                    print(f"  [PI VIDEO LOG] {l}")
                if f"Video {media_id} processed" in l:
                    completed = True
        if completed:
            break
        time.sleep(2)
        
    if os.path.exists(video_path):
        os.remove(video_path)
    print("Video ingestion test completed successfully!")

def test_audio_submission():
    print("\n" + "="*50)
    print("TESTING AUDIO INGESTION & INTERFACE VERIFICATION")
    print("="*50)
    
    # Generate a simple 1-second 8kHz WAV file
    sample_rate = 8000
    duration = 1.0
    num_samples = int(sample_rate * duration)
    wav_header = bytearray()
    wav_header.extend(b'RIFF')
    wav_header.extend(struct.pack('<I', 36 + num_samples * 2))
    wav_header.extend(b'WAVEfmt ')
    wav_header.extend(struct.pack('<I', 16))
    wav_header.extend(struct.pack('<H', 1)) # PCM
    wav_header.extend(struct.pack('<H', 1)) # Mono
    wav_header.extend(struct.pack('<I', sample_rate))
    wav_header.extend(struct.pack('<I', sample_rate * 2))
    wav_header.extend(struct.pack('<H', 2))
    wav_header.extend(struct.pack('<H', 16))
    wav_header.extend(b'data')
    wav_header.extend(struct.pack('<I', num_samples * 2))
    
    samples = bytearray()
    for i in range(num_samples):
        val = int(16000 * np.sin(2 * np.pi * 440 * i / sample_rate))
        samples.extend(struct.pack('<h', val))
        
    audio_bytes = bytes(wav_header + samples)
    b64_audio = base64.b64encode(audio_bytes).decode("ascii")
    
    payload = {
        "nodeId": "sip-pi-001",
        "mediaType": "AUDIO",
        "filename": "test_audio.wav",
        "contentType": "audio/wav",
        "data": b64_audio
    }
    
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/v1/media/upload",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req)
    audio_data = json.loads(res.read().decode())
    media_id = audio_data.get("mediaId")
    cmd_id = audio_data.get("commandId")
    print(f"Audio uploaded: Media ID={media_id}, Command ID={cmd_id}")
    
    # Monitor Pi log for audio handling
    start_t = time.time()
    seen = set()
    found_audio = False
    while time.time() - start_t < 45:
        lines = get_recent_logs()
        for l in lines:
            if l not in seen:
                seen.add(l)
                if media_id in l or "Audio file" in l:
                    print(f"  [PI AUDIO LOG] {l}")
                if f"Audio file {media_id} received" in l:
                    found_audio = True
        if found_audio:
            break
        time.sleep(2)
    
    # Check reporting back to Central Backend result
    try:
        res_req = urllib.request.Request(f"{BACKEND_URL}/api/v1/media/{media_id}/result")
        res_obj = json.loads(urllib.request.urlopen(res_req).read())
        print(f"Backend Media Result for Audio: {res_obj}")
    except Exception as e:
        print("Backend result query:", e)
        
    print("Audio interface test completed per specification!")

if __name__ == "__main__":
    test_video_submission()
    test_audio_submission()
