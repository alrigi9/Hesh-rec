import io, wave, struct, requests, json, time, sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def test_full_pipeline():
    print("[*] Running End-to-End Verification Pipeline...")
    
    # 1. Generate 5-second test WAV audio
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack('<h', 0) * 16000 * 5)
    audio_bytes = buf.getvalue()
    
    # 2. Test Direct Groq Audio Transcription
    groq_res = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": "Bearer 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"},
        files={"file": ("test.wav", audio_bytes, "audio/wav")},
        data={"model": "whisper-large-v3"}
    )
    if groq_res.status_code != 200:
        raise Exception(f"Groq Direct Transcription Failed: {groq_res.status_code} - {groq_res.text}")
    print("[+] Step 1 (Groq Direct Transcription): SUCCESS")
    
    # 3. Test Synthesis API Route on Production
    synthesis_payload = {
        "transcript": "In today's engineering sync, Hesham confirmed the Heroku backend deployment and verified the SOC 2 security review.",
        "language": "en",
        "template": "Executive Summary"
    }
    synth_res = requests.post(
        "https://recmap.tech/api/process-audio",
        json=synthesis_payload,
        timeout=45
    )
    if synth_res.status_code != 200:
        raise Exception(f"Synthesis Route Failed: {synth_res.status_code} - {synth_res.text}")
    
    data = synth_res.json()
    assert "summary" in data and len(data["summary"]) > 0, "Summary is empty"
    assert "action_items" in data and len(data["action_items"]) > 0, "Action items empty"
    assert "mindmap_markdown" in data and len(data["mindmap_markdown"]) > 0, "Mindmap empty"
    print("[+] Step 2 (Gemini Intelligence Extraction): SUCCESS")
    print(f"[*] Title: {data.get('title')}")
    print(f"[*] Summary Preview: {data.get('summary')[:100]}...")
    print(f"[*] Action Items Count: {len(data.get('action_items', []))}")
    print(f"[*] Mindmap Valid: {data.get('mindmap_markdown', '').startswith('#')}")
    print("\n[OK] ALL PRODUCTION SYSTEMS VERIFIED AND OPERATIONAL!")

if __name__ == "__main__":
    test_full_pipeline()
