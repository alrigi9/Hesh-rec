import requests

supabase_url = "https://bdgjsmwtxfacgqqhwtzw.supabase.co"
service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJkZ2pzbXd0eGZhY2dxcWh3dHp3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzU1MjI0NSwiZXhwIjoyMTAzMTI4MjQ1fQ.X4zJ5iLD8gyjrcoX8uy0GJwE1eCvPQLMxvNRM1kvHG4"

headers = {
    "apikey": service_key,
    "Authorization": f"Bearer {service_key}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

print("[*] Searching for sessions in Supabase...")
res = requests.get(f"{supabase_url}/rest/v1/sessions?select=*", headers=headers)
if res.status_code == 200:
    records = res.json()
    print(f"Total session records in DB: {len(records)}")
    for r in records:
        title = r.get("title", "")
        sid = r.get("id")
        user_id = r.get("user_id")
        print(f"  Session ID: {sid} | Title: {title} | UserID: {user_id}")
        del_r = requests.delete(f"{supabase_url}/rest/v1/sessions?id=eq.{sid}", headers=headers)
        print(f"    Deleted {sid}: status {del_r.status_code}")
else:
    print(f"[-] Supabase query failed: {res.status_code} - {res.text}")

print("[*] Checking /api/sessions endpoint...")
try:
    local_api_res = requests.get("https://recmap.tech/api/sessions")
    print(f"Live /api/sessions response: status {local_api_res.status_code}")
    print(f"Live data: {local_api_res.json()}")
except Exception as e:
    print(f"Error checking live sessions: {e}")
