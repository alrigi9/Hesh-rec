import sys
import io
import json
import uuid
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

def run_e2e_persistence_test():
    print("=" * 70)
    print("[*] STARTING COMPREHENSIVE E2E PERSISTENCE & DATA SYNC TEST")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # STEP 1: Authenticate Test User Against Supabase
    # -------------------------------------------------------------------------
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
    if link_res.status_code != 200:
        raise AssertionError(f"Generate magic link failed: {link_res.status_code} - {link_res.text}")

    otp = link_res.json().get("email_otp")
    if not otp:
        raise AssertionError("No email OTP returned from Supabase Admin generate_link")

    verify_res = requests.post(
        f"{SUPABASE_URL}/auth/v1/verify",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Content-Type": "application/json",
        },
        json={"type": "magiclink", "email": TEST_USER_EMAIL, "token": otp},
        timeout=15,
    )
    if verify_res.status_code != 200:
        raise AssertionError(f"User OTP verification failed: {verify_res.status_code} - {verify_res.text}")

    auth_data = verify_res.json()
    user_token = auth_data.get("access_token")
    user_id = auth_data.get("user", {}).get("id")

    assert user_token, "Access token must not be empty"
    assert user_id == EXPECTED_USER_ID, f"Expected user_id {EXPECTED_USER_ID}, got {user_id}"
    print(f"  [+] User authenticated successfully: {TEST_USER_EMAIL} (UID: {user_id})")

    # -------------------------------------------------------------------------
    # STEP 2: Process Audio Ingestion via Production API Route
    # -------------------------------------------------------------------------
    print("\n[Step 2] Ingesting meeting transcript via /api/process-audio...")
    meeting_title = f"Automated E2E Persistence Validation {uuid.uuid4().hex[:6]}"
    sample_transcript = (
        "In this quarterly technical review, Hesham presented the multi-device sync architecture. "
        "The engineering team agreed to enforce Supabase session persistence across mobile and desktop. "
        "Action item: Hesham to finalize the automated verification suite by end of week. "
        "Action item: Sarah to review cross-platform responsive styling for iOS Safari."
    )

    process_payload = {
        "title": meeting_title,
        "transcript": sample_transcript,
        "transcript_text": sample_transcript,
        "template": "Executive Summary",
        "language": "en",
        "user_id": user_id,
        "duration_seconds": 120,
    }

    process_res = requests.post(
        f"{BASE_URL}/api/process-audio",
        headers={
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
        },
        json=process_payload,
        timeout=45,
    )
    if process_res.status_code != 200:
        raise AssertionError(f"/api/process-audio failed: {process_res.status_code} - {process_res.text}")

    session_data = process_res.json()
    session_id = session_data.get("id")

    # Strict validations on returned session payload
    assert session_id, "Session ID must be returned"
    assert session_data.get("title"), "Session title must not be empty"
    assert session_data.get("summary") or session_data.get("executive_summary"), "Summary must not be empty"
    assert isinstance(session_data.get("action_items"), list) and len(session_data["action_items"]) > 0, "Action items must be non-empty list"
    assert isinstance(session_data.get("sections") or session_data.get("discussion_pillars"), list), "Sections must be list"
    assert session_data.get("mindmap_markdown") and session_data["mindmap_markdown"].startswith("#"), "Mindmap must start with #"
    assert session_data.get("user_id") == user_id, "Returned user_id must match authenticated user"

    print(f"  [+] Session created: ID={session_id}")
    print(f"  [+] Title: {session_data.get('title')}")
    print(f"  [+] Action items count: {len(session_data.get('action_items', []))}")
    print(f"  [+] Mind map valid: True")

    # -------------------------------------------------------------------------
    # STEP 3: Verify Direct Supabase DB Table Commitment (with User Token)
    # -------------------------------------------------------------------------
    print("\n[Step 3] Verifying row in Supabase 'sessions' table with user token...")
    db_query_res = requests.get(
        f"{SUPABASE_URL}/rest/v1/sessions?id=eq.{session_id}&select=*",
        headers={
            "Authorization": f"Bearer {user_token}",
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
        },
        timeout=15,
    )
    if db_query_res.status_code != 200:
        raise AssertionError(f"Direct Supabase query failed: {db_query_res.status_code} - {db_query_res.text}")

    db_rows = db_query_res.json()
    assert len(db_rows) == 1, f"Expected exactly 1 committed row in Supabase, found {len(db_rows)}"
    row = db_rows[0]

    assert row.get("id") == session_id, "Committed ID mismatch"
    assert row.get("title"), "Committed title must not be empty"
    assert row.get("summary") or row.get("executive_summary"), "Committed summary must not be empty"
    assert isinstance(row.get("action_items"), list) and len(row["action_items"]) > 0, "Committed action items must be non-empty list"
    assert row.get("mindmap_markdown") and row["mindmap_markdown"].startswith("#"), "Committed mindmap must start with #"
    
    meta = row.get("strategic_insights") or {}
    assert meta.get("user_id") == user_id, f"Stored user_id in strategic_insights must be {user_id}"
    print("  [+] Supabase 'sessions' table commitment confirmed with 100% field integrity.")

    # -------------------------------------------------------------------------
    # STEP 4: Verify /api/sessions Hydration (Simulating Mobile & Desktop Mount)
    # -------------------------------------------------------------------------
    print("\n[Step 4] Querying /api/sessions endpoint as authenticated user...")
    sessions_res = requests.get(
        f"{BASE_URL}/api/sessions?user_id={user_id}",
        headers={
            "Authorization": f"Bearer {user_token}",
        },
        timeout=15,
    )
    if sessions_res.status_code != 200:
        raise AssertionError(f"/api/sessions query failed: {sessions_res.status_code} - {sessions_res.text}")

    user_sessions = sessions_res.json()
    assert isinstance(user_sessions, list) and len(user_sessions) > 0, "User sessions list must not be empty"

    matched = next((s for s in user_sessions if s.get("id") == session_id), None)
    assert matched is not None, f"Newly created session {session_id} not found in user sessions list"
    assert matched.get("title") == meeting_title or session_data.get("title") in matched.get("title"), "Title mismatch in sessions list"
    assert matched.get("summary") or matched.get("executive_summary"), "Summary missing in hydrated session list item"
    assert len(matched.get("action_items", [])) > 0, "Action items missing in hydrated session list item"
    assert matched.get("mindmap_markdown", "").startswith("#"), "Mindmap missing in hydrated session list item"

    print(f"  [+] Hydration verified: {len(user_sessions)} total sessions available for user.")

    # -------------------------------------------------------------------------
    # STEP 5: Verify Single Session Query /api/sessions/[id]
    # -------------------------------------------------------------------------
    print(f"\n[Step 5] Querying /api/sessions/{session_id} directly...")
    single_res = requests.get(
        f"{BASE_URL}/api/sessions/{session_id}",
        headers={
            "Authorization": f"Bearer {user_token}",
        },
        timeout=15,
    )
    if single_res.status_code != 200:
        raise AssertionError(f"/api/sessions/{session_id} failed: {single_res.status_code} - {single_res.text}")

    single_data = single_res.json()
    assert single_data.get("id") == session_id, "Single session ID mismatch"
    assert len(single_data.get("action_items", [])) > 0, "Single session action items empty"
    print("  [+] Single session endpoint verified.")

    # -------------------------------------------------------------------------
    # STEP 6: Verify Contextual Chat Assistant on Session
    # -------------------------------------------------------------------------
    print("\n[Step 6] Testing AI Meeting Assistant /api/chat with session context...")
    chat_res = requests.post(
        f"{BASE_URL}/api/chat",
        headers={
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
        },
        json={
            "session": single_data,
            "query": "What are the key action items agreed upon in this meeting?",
        },
        timeout=25,
    )
    if chat_res.status_code != 200:
        raise AssertionError(f"/api/chat failed: {chat_res.status_code} - {chat_res.text}")

    chat_data = chat_res.json()
    assert chat_data.get("answer") and len(chat_data["answer"]) > 10, "Chat answer must be non-empty"
    print(f"  [+] AI Assistant Answer: {chat_data['answer'][:120]}...")

    print("\n" + "=" * 70)
    print("[SUCCESS] ALL 6 END-TO-END PERSISTENCE & HYDRATION TESTS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    run_e2e_persistence_test()
