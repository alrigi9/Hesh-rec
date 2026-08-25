import sys
import io
import wave
import struct
import math
import time
import requests

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SUPABASE_URL = "https://bdgjsmwtxfacgqqhwtzw.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJkZ2pzbXd0eGZhY2dxcWh3dHp3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzU1MjI0NSwiZXhwIjoyMTAzMTI4MjQ1fQ."
    "X4zJ5iLD8gyjrcoX8uy0GJwE1eCvPQLMxvNRM1kvHG4"
)
BASE_URL = "https://recmap.tech"
TEST_USER_EMAIL = "h.alraiqe@gmail.com"
EXPECTED_USER_ID = "f3fa0111-b1d9-4d98-a5ef-90dfea02443e"

def create_large_audio_file(target_mb: float = 8.2) -> bytes:
    """Generate a real valid WAV audio file of ~8.2MB with synthesized tone"""
    sample_rate = 44100
    num_channels = 2
    sampwidth = 2  # 16-bit
    bytes_per_second = sample_rate * num_channels * sampwidth  # 176,400 bytes/sec
    target_bytes = int(target_mb * 1024 * 1024)
    duration_seconds = target_bytes / bytes_per_second
    total_frames = int(duration_seconds * sample_rate)

    print(f"[*] Generating {target_mb:.2f}MB test audio payload ({duration_seconds:.1f}s PCM WAV)...")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(num_channels)
        wav_file.setsampwidth(sampwidth)
        wav_file.setframerate(sample_rate)

        # Generate audio frames in chunks to optimize memory
        chunk_frames = 44100
        frequency = 440.0  # 440 Hz standard concert A tone
        frames_written = 0

        while frames_written < total_frames:
            current_chunk = min(chunk_frames, total_frames - frames_written)
            frame_data = bytearray()
            for i in range(current_chunk):
                t = (frames_written + i) / sample_rate
                # Generate gentle audible sine wave
                value = int(8000.0 * math.sin(2.0 * math.pi * frequency * t))
                # Left & right stereo channels
                frame_data.extend(struct.pack("<hh", value, value))
            wav_file.writeframes(frame_data)
            frames_written += current_chunk

    wav_bytes = buffer.getvalue()
    print(f"[+] Generated valid WAV audio file: {len(wav_bytes) / (1024 * 1024):.2f} MB")
    return wav_bytes

def run_large_audio_e2e_test():
    print("=" * 75)
    print("[*] STARTING LARGE AUDIO (>8MB) DIRECT-TO-STORAGE E2E VALIDATION TEST")
    print("=" * 75)

    # 1. Authenticate Test User
    print("\n[Step 1] Authenticating user against Supabase Auth...")
    link_res = requests.post(
        f"{SUPABASE_URL}/auth/v1/admin/generate_link",
        headers={
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Content-Type": "application/json",
        },
        json={"type": "magiclink", "email": TEST_USER_EMAIL},
        timeout=15,
    )
    otp = link_res.json().get("email_otp")
    verify_res = requests.post(
        f"{SUPABASE_URL}/auth/v1/verify",
        headers={"apikey": SUPABASE_SERVICE_ROLE_KEY, "Content-Type": "application/json"},
        json={"type": "magiclink", "email": TEST_USER_EMAIL, "token": otp},
        timeout=15,
    )
    user_token = verify_res.json().get("access_token")
    user_id = verify_res.json().get("user", {}).get("id")
    print(f"  [+] User authenticated: UID={user_id}")

    # 2. Generate Real 8.2MB Audio Binary
    audio_bytes = create_large_audio_file(target_mb=8.2)
    filename = f"large_mobile_recording_{int(time.time())}.wav"

    # 3. Request Direct-to-Storage Signed Upload URL
    print("\n[Step 2] Requesting signed direct-to-storage upload URL from /api/upload-url...")
    upload_url_res = requests.post(
        f"{BASE_URL}/api/upload-url",
        headers={
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
        },
        json={"filename": filename, "user_id": user_id},
        timeout=15,
    )
    if upload_url_res.status_code != 200:
        raise AssertionError(f"Failed to get upload URL: {upload_url_res.status_code} - {upload_url_res.text}")

    upload_data = upload_url_res.json()
    upload_url = upload_data.get("upload_url")
    public_file_url = upload_data.get("file_url")
    assert upload_url and public_file_url, "Must return upload_url and file_url"
    print(f"  [+] Signed upload URL acquired: {upload_url[:70]}...")

    # 4. Stream 8.2MB Binary directly into Supabase Storage Bucket
    print(f"\n[Step 3] Streaming 8.2MB binary directly to Supabase Storage (Bypassing Vercel 4.5MB limit)...")
    start_time = time.time()
    put_res = requests.put(
        upload_url,
        headers={"Content-Type": "audio/wav"},
        data=audio_bytes,
        timeout=60,
    )
    upload_duration = time.time() - start_time
    if put_res.status_code not in (200, 201):
        raise AssertionError(f"Direct storage upload failed: {put_res.status_code} - {put_res.text}")
    print(f"  [+] Direct storage stream succeeded in {upload_duration:.2f}s (Status {put_res.status_code})")

    # 5. Process Audio via /api/process-audio passing only lightweight JSON
    print(f"\n[Step 4] Triggering processing pipeline via lightweight JSON /api/process-audio...")
    synth_payload = {
        "file_url": public_file_url,
        "filename": filename,
        "template": "Executive Summary",
        "language": "en",
        "custom_title": "Executive Product Review: Scalable Audio Architecture",
        "user_id": user_id,
        "duration_seconds": 48,
    }
    
    proc_start = time.time()
    proc_res = requests.post(
        f"{BASE_URL}/api/process-audio",
        headers={
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
        },
        json=synth_payload,
        timeout=90,
    )
    proc_duration = time.time() - proc_start

    if proc_res.status_code != 200:
        raise AssertionError(f"/api/process-audio failed: {proc_res.status_code} - {proc_res.text}")

    session = proc_res.json()
    session_id = session.get("id")
    print(f"  [+] Audio processed successfully in {proc_duration:.2f}s!")
    print(f"  [+] Session ID: {session_id}")
    print(f"  [+] Title: {session.get('title')}")
    print(f"  [+] Action items: {len(session.get('action_items', []))}")
    print(f"  [+] Mindmap generated: {session.get('mindmap_markdown', '').startswith('#')}")

    # 6. Verify Direct Database Persistence
    print(f"\n[Step 5] Verifying persistent database record in Supabase 'sessions' table...")
    db_res = requests.get(
        f"{SUPABASE_URL}/rest/v1/sessions?id=eq.{session_id}&select=*",
        headers={
            "Authorization": f"Bearer {user_token}",
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
        },
        timeout=15,
    )
    rows = db_res.json()
    assert len(rows) == 1, f"Expected 1 record in DB, found {len(rows)}"
    assert rows[0].get("id") == session_id
    assert rows[0].get("title")
    print("  [+] Supabase 'sessions' table row confirmed committed.")

    # 7. Verify Hydration on /api/sessions
    print(f"\n[Step 6] Verifying instant hydration on /api/sessions...")
    sessions_res = requests.get(
        f"{BASE_URL}/api/sessions?user_id={user_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        timeout=15,
    )
    sessions_list = sessions_res.json()
    assert any(s.get("id") == session_id for s in sessions_list), "Session not found in hydrated sessions list"
    print(f"  [+] Hydration verified: Session is immediately available across all user devices.")

    print("\n" + "=" * 75)
    print("[SUCCESS] LARGE AUDIO (8.2MB) DIRECT-TO-STORAGE PIPELINE FULLY VALIDATED!")
    print("=" * 75)

if __name__ == "__main__":
    run_large_audio_e2e_test()
