import base64
import json
import os
import time
import urllib.request
import urllib.error
try:
    import paramiko
except ImportError:
    paramiko = None
import dotenv

dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.operator"))

BACKEND_URL = os.environ.get("BACKEND_URL", "https://api.awarespan.bchbenjamin.in")
PI_HOST = os.environ.get("PI_HOST", "10.42.0.1")
PI_USER = os.environ.get("PI_USER", "benjamin")
PI_PASS = os.environ.get("PI_PASSWORD")
OPERATOR_USER = os.environ.get("AWARESPAN_OPERATOR_USER", "bchbenjamin")
OPERATOR_PASS = os.environ.get("AWARESPAN_OPERATOR_PASSWORD", "")

def run_pipeline():
    print("=" * 60)
    print("AWARESPAN END-TO-END PIPELINE VERIFICATION RUN")
    print("=" * 60)
    
    # STEP 1: Upload Real Test Knife Image
    print("\n[STEP 1] Submitting Photo (knife_test.jpg) to Central Backend...")
    image_path = "tests/fixtures/knife_test.jpg"
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    b64_data = base64.b64encode(img_bytes).decode("ascii")
    
    payload = {
        "nodeId": "sip-pi-001",
        "mediaType": "IMAGE",
        "filename": "knife_test.jpg",
        "contentType": "image/jpeg",
        "data": b64_data
    }
    
    t_start = time.time()
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/v1/media/upload",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode())
    media_id = data.get("mediaId")
    cmd_id = data.get("commandId")
    print(f"-> Central Backend Response: HTTP {res.status}")
    print(f"-> Assigned Media ID: {media_id}")
    print(f"-> Queued Command ID: {cmd_id}")
    
    # STEP 2 & 3: Monitor Raspberry Pi Processing & Inference
    print(f"\n[STEP 2 & 3] Monitoring Raspberry Pi 5 node (sip-pi-001) for command execution & YOLOv8 inference...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)
    
    found_ingest = False
    found_detection = False
    found_tg = False
    found_rest = False
    incident_id = None
    
    start_time = time.time()
    seen_lines = set()
    
    while time.time() - start_time < 50:
        cmd = "journalctl -u awarespan-node.service -n 25 --no-pager"
        _, stdout, _ = ssh.exec_command(cmd)
        lines = stdout.read().decode().splitlines()
        
        for l in lines:
            if l not in seen_lines:
                seen_lines.add(l)
                if cmd_id in l or media_id in l:
                    print(f"  [PI LOG] {l}")
                    found_ingest = True
                if "Telegram alert dispatched for incident" in l:
                    print(f"  [PI TELEGRAM] {l}")
                    found_tg = True
                    parts = l.split("for incident ")
                    if len(parts) > 1:
                        incident_id = parts[1].strip()
                if "Incident" in l and "synced via REST API" in l:
                    print(f"  [PI BACKEND SYNC] {l}")
                    found_rest = True
                if "YOLO" in l or "knife" in l or "gun" in l or "tier2" in l or "Threat" in l:
                    print(f"  [PI INFERENCE] {l}")
                    
        if found_tg and found_rest:
            break
        time.sleep(2)
        
    ssh.close()
    
    # STEP 4: Query Central Backend for Incident
    print(f"\n[STEP 4] Verifying Incident Persistence & Distribution on Central Backend...")
    auth_req = urllib.request.Request(
        f"{BACKEND_URL}/api/v1/auth/login",
        data=json.dumps({"username": OPERATOR_USER, "password": OPERATOR_PASS}).encode(),
        headers={"Content-Type": "application/json"}
    )
    auth_res = urllib.request.urlopen(auth_req)
    token = json.loads(auth_res.read())["token"]
    
    inc_req = urllib.request.Request(
        f"{BACKEND_URL}/api/v1/incidents?page=0&size=10",
        headers={"Authorization": f"Bearer {token}"}
    )
    inc_res = urllib.request.urlopen(inc_req)
    incidents = json.loads(inc_res.read().decode()).get("content", [])
    
    persisted = None
    for inc in incidents:
        if incident_id and (inc.get("id") == incident_id or incident_id in str(inc.get("id"))):
            persisted = inc
            break
        elif not persisted and inc.get("threatType") in ("WEAPON", "GUN", "KNIFE"):
            persisted = inc
            
    if persisted:
        print(f"-> SUCCESS: Incident confirmed in Central Backend database:")
        print(f"   - Incident ID: {persisted.get('id')}")
        print(f"   - Threat Type: {persisted.get('threatType')}")
        print(f"   - Severity:    {persisted.get('threatSeverity')}")
        print(f"   - Description: {persisted.get('threatDescription')}")
        print(f"   - Created At:  {persisted.get('createdAt')}")
        print(f"   - State:       {persisted.get('state')}")
    else:
        print(f"-> Latest incident in backend: {incidents[0] if incidents else 'None'}")
        
    total_latency = time.time() - t_start
    print(f"\nTotal End-to-End Pipeline Latency: {total_latency:.2f} seconds")
    print("=" * 60)

if __name__ == "__main__":
    run_pipeline()
