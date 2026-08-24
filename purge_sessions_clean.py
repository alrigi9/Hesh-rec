import os
import shutil
from pathlib import Path
import requests

supabase_url = "https://bdgjsmwtxfacgqqhwtzw.supabase.co"
service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJkZ2pzbXd0eGZhY2dxcWh3dHp3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzU1MjI0NSwiZXhwIjoyMTAzMTI4MjQ1fQ.X4zJ5iLD8gyjrcoX8uy0GJwE1eCvPQLMxvNRM1kvHG4"

headers = {
    "apikey": service_key,
    "Authorization": f"Bearer {service_key}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

print("[*] Deleting all sessions in Supabase...")
res = requests.get(f"{supabase_url}/rest/v1/sessions?select=*", headers=headers)
if res.status_code == 200:
    items = res.json()
    print(f"Found {len(items)} session records.")
    for it in items:
        sid = it.get("id")
        d_res = requests.delete(f"{supabase_url}/rest/v1/sessions?id=eq.{sid}", headers=headers)
        print(f"  Deleted session {sid}: status {d_res.status_code}")

# Check remaining count
verify = requests.get(f"{supabase_url}/rest/v1/sessions?select=id", headers=headers)
print(f"Remaining Supabase sessions: {len(verify.json()) if verify.ok else 'error'}")

# Clean local sessions folder
local_sessions_dir = Path("D:/claude/Hesh rec/sessions")
if local_sessions_dir.exists():
    for f in local_sessions_dir.glob("*.json"):
        if f.name != "profiles.json":
            try:
                f.unlink()
                print(f"Deleted local session file: {f.name}")
            except Exception as e:
                print(f"Error deleting {f.name}: {e}")

print("[*] Purge complete!")
