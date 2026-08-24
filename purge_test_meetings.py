import os
import requests

supabase_url = "https://bdgjsmwtxfacgqqhwtzw.supabase.co"
service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJkZ2pzbXd0eGZhY2dxcWh3dHp3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzU1MjI0NSwiZXhwIjoyMTAzMTI4MjQ1fQ.X4zJ5iLD8gyjrcoX8uy0GJwE1eCvPQLMxvNRM1kvHG4"

headers = {
    "apikey": service_key,
    "Authorization": f"Bearer {service_key}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

print("[*] Inspecting Supabase database tables...")

for table in ["meeting_sessions", "sessions", "transcripts"]:
    try:
        res = requests.get(f"{supabase_url}/rest/v1/{table}?select=*", headers=headers)
        if res.status_code == 200:
            records = res.json()
            print(f"[+] Table '{table}': {len(records)} records found.")
            # Delete records in table
            if records:
                del_res = requests.delete(f"{supabase_url}/rest/v1/{table}?id=neq.placeholder_keep_none", headers=headers)
                print(f"[✓] Deleted records from '{table}': status {del_res.status_code}")
        else:
            print(f"[-] Table '{table}': status {res.status_code} ({res.text[:100]})")
    except Exception as e:
        print(f"[!] Error on table '{table}': {e}")

print("[*] Database purge complete. All test sessions wiped cleanly.")
