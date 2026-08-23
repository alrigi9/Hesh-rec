import sys
import time
import threading
from pathlib import Path

# Enforce UTF-8 standard streams on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import soundcard as sc

def run_diagnostic():
    print("=" * 65)
    print("🎙️  AUDIO CAPTURE & LOOPBACK DIAGNOSTIC")
    print("=" * 65)

    # 1. Device Discovery
    print("\n[1] DETECTED AUDIO ENDPOINTS:")
    try:
        spk = sc.default_speaker()
        print(f"  • Default Speaker:    {spk.name} ({spk.channels} channels)")
    except Exception as e:
        spk = None
        print(f"  • Default Speaker:    ERROR ({e})")

    try:
        mic = sc.default_microphone()
        print(f"  • Default Microphone: {mic.name} ({mic.channels} channels)")
    except Exception as e:
        mic = None
        print(f"  • Default Microphone: ERROR ({e})")

    all_mics = sc.all_microphones(include_loopback=True)
    print(f"  • Total Audio Endpoints (including WASAPI Loopback): {len(all_mics)}")

    sr = 16000
    duration = 3.0
    num_frames = int(sr * duration)

    # 2. Live Sound Playback + Loopback Capture Verification
    print("\n[2] TESTING SPEAKER WASAPI LOOPBACK (Sound Playback + Capture)...")
    if spk:
        try:
            loop_mic = sc.get_microphone(spk.name, include_loopback=True)
            print(f"  • Target Loopback Device: {loop_mic.name}")

            # Generate a 440Hz test tone
            t = np.linspace(0, duration, num_frames, endpoint=False)
            tone = 0.25 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
            tone_multi = np.repeat(tone[:, np.newaxis], spk.channels, axis=1)

            captured_loop = None

            def play_tone():
                try:
                    with spk.player(samplerate=sr, channels=spk.channels) as p:
                        p.play(tone_multi)
                except Exception as ex:
                    print(f"    [Play Warning]: {ex}")

            def record_loop():
                nonlocal captured_loop
                try:
                    with loop_mic.recorder(samplerate=sr, channels=1) as r:
                        captured_loop = r.record(numframes=num_frames)
                except Exception as ex:
                    print(f"    [Record Warning]: {ex}")

            t_rec = threading.Thread(target=record_loop)
            t_play = threading.Thread(target=play_tone)

            t_rec.start()
            time.sleep(0.05)
            t_play.start()

            t_rec.join()
            t_play.join()

            if captured_loop is not None:
                rms = float(np.sqrt(np.mean(captured_loop ** 2)))
                peak = float(np.max(np.abs(captured_loop)))
                print(f"  • Recorded Frames: {captured_loop.shape[0]} ({duration}s @ {sr}Hz)")
                print(f"  • RMS Energy Level: {rms:.6f}")
                print(f"  • Peak Amplitude:   {peak:.6f}")
                if rms > 0.001:
                    print("  • Result: ✅ [PASS] Speaker loopback captured live sound (RMS > 0)")
                else:
                    print("  • Result: ⚠️ [WARNING] Loopback captured silence")
        except Exception as e:
            print(f"  • Loopback Test Error: {e}")
    else:
        print("  • No default speaker found.")

    # 3. Microphone Capture Test
    print("\n[3] TESTING MICROPHONE CAPTURE (3 Seconds)...")
    if mic:
        try:
            print(f"  • Recording from: {mic.name}")
            with mic.recorder(samplerate=sr, channels=1) as r:
                data_mic = r.record(numframes=num_frames)

            rms_m = float(np.sqrt(np.mean(data_mic ** 2)))
            peak_m = float(np.max(np.abs(data_mic)))
            print(f"  • Recorded Frames: {data_mic.shape[0]} ({duration}s @ {sr}Hz)")
            print(f"  • RMS Energy Level: {rms_m:.6f}")
            print(f"  • Peak Amplitude:   {peak_m:.6f}")
            if rms_m > 0.001:
                print("  • Result: ✅ [PASS] Microphone active voice detected (RMS > 0)")
            else:
                print("  • Result: ℹ️ [IDLE] Microphone is currently quiet / muted")
        except Exception as e:
            print(f"  • Mic Test Error: {e}")
    else:
        print("  • No default microphone found.")

    print("\n" + "=" * 65)
    print("DIAGNOSTIC RUN COMPLETED SUCCESSFULLY")
    print("=" * 65)

if __name__ == "__main__":
    run_diagnostic()
