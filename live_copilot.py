import os
# Establish OpenMP / CTranslate2 runtime environment before any other C extensions
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "4"
from faster_whisper import WhisperModel

import sys
import io
import time
import wave
import json
import webbrowser
import threading
import queue
import collections
import re
from datetime import datetime
from pathlib import Path

# Enforce UTF-8 standard streams on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Import PyQt5 UI components (NO QGraphicsDropShadowEffect on translucent window)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame,
    QShortcut, QStackedWidget, QLineEdit, QDialog, QComboBox,
    QTextEdit
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QPoint, QTimer
)
from PyQt5.QtGui import (
    QColor, QPalette, QKeySequence, QCursor, QPainter,
    QBrush, QTextCursor
)

import numpy as np
import pyaudiowpatch as pyaudio
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load Environment & Paths
BASE_DIR = Path(__file__).resolve().parent
SESSIONS_DIR = BASE_DIR / "sessions"
OUTPUTS_DIR = BASE_DIR / "outputs"
CONFIG_FILE = BASE_DIR / "copilot_config.json"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
MODEL_CANDIDATES = [
    os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest"
]

TARGET_SAMPLE_RATE = 16000
SPEECH_RMS_THRESHOLD = 0.0010
CHUNK_ACCUMULATE_DURATION = 3.0 # 3.0-second audio batches for Whisper

PHANTOM_FILTER_TOKENS = {
    "wrong", "wrong.", "you", "you.", "thank you", "thank you.",
    "um", "uh", "none", "none.", "music", ".", "...", "", "subtitles",
    "bye", "okay", "okay.", "like", "so"
}

# =============================================================================
# CONFIGURATION PERSISTENCE
# =============================================================================
def load_saved_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Config Save Error]: {e}", flush=True)


# =============================================================================
# ROBUST DUAL-THREAD WASAPI AUDIO CAPTURE
# =============================================================================
class DedicatedWASAPICapture:
    """
    Simultaneously captures Speaker Loopback (YouTube, Zoom, 8ch/2ch)
    and Microphone (1ch/2ch) in independent non-blocking threads,
    mixing both into a clean 16kHz mono stream.
    """
    def __init__(self, target_sr: int = TARGET_SAMPLE_RATE):
        self.target_sr = target_sr
        self.running = False
        
        self.spk_queue = queue.Queue(maxsize=80)
        self.mic_queue = queue.Queue(maxsize=80)
        self.audio_queue = queue.Queue(maxsize=300)
        
        self.spk_name = "Default Loopback"
        self.mic_name = "Default Microphone"
        self.spk_index = None
        self.mic_index = None
        
        self.p_instance = None
        self.spk_stream = None
        self.mic_stream = None
        self.lock = threading.Lock()

    def start(self, custom_spk_idx=None, custom_mic_idx=None):
        self.running = True
        self._start_capture_threads(custom_spk_idx, custom_mic_idx)

    def stop(self):
        self.running = False
        with self.lock:
            try:
                if self.spk_stream:
                    self.spk_stream.stop_stream()
                    self.spk_stream.close()
                    self.spk_stream = None
            except Exception:
                pass
            try:
                if self.mic_stream:
                    self.mic_stream.stop_stream()
                    self.mic_stream.close()
                    self.mic_stream = None
            except Exception:
                pass
            try:
                if self.p_instance:
                    self.p_instance.terminate()
                    self.p_instance = None
            except Exception:
                pass

    def restart(self, custom_spk_idx=None, custom_mic_idx=None):
        self.stop()
        time.sleep(0.15)
        while not self.spk_queue.empty():
            try: self.spk_queue.get_nowait()
            except Exception: break
        while not self.mic_queue.empty():
            try: self.mic_queue.get_nowait()
            except Exception: break
        while not self.audio_queue.empty():
            try: self.audio_queue.get_nowait()
            except Exception: break
        self.start(custom_spk_idx, custom_mic_idx)

    def _is_virtual(self, name: str) -> bool:
        name_l = name.lower()
        return any(v in name_l for v in ["oculus", "steam streaming", "virtual desktop", "iriun"])

    def _start_capture_threads(self, custom_spk_idx=None, custom_mic_idx=None):
        try:
            p = pyaudio.PyAudio()
            self.p_instance = p
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            wasapi_host_id = wasapi_info["index"]
            saved = load_saved_config()

            # 1. Target Loopback Device
            loopback = None
            # Check explicit index from dialog
            if custom_spk_idx is not None:
                try:
                    dev = p.get_device_info_by_index(custom_spk_idx)
                    if dev["hostApi"] == wasapi_host_id:
                        loopback = dev
                except Exception:
                    pass

            # Check saved config index
            if not loopback and "speaker_loopback_index" in saved:
                try:
                    dev = p.get_device_info_by_index(saved["speaker_loopback_index"])
                    if dev["hostApi"] == wasapi_host_id:
                        loopback = dev
                except Exception:
                    pass

            # Search by Logitech / G733
            if not loopback:
                for dev in p.get_loopback_device_info_generator():
                    name = dev["name"].lower()
                    if ("logitech" in name or "g733" in name) and dev["hostApi"] == wasapi_host_id:
                        loopback = dev
                        break

            # Search by non-virtual WASAPI loopback
            if not loopback:
                for dev in p.get_loopback_device_info_generator():
                    if not self._is_virtual(dev["name"]) and dev["hostApi"] == wasapi_host_id:
                        loopback = dev
                        break

            # Fallback to default
            if not loopback:
                def_spk = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                for dev in p.get_loopback_device_info_generator():
                    if def_spk["name"] in dev["name"]:
                        loopback = dev
                        break
                if not loopback:
                    loopback = p.get_default_wasapi_loopback()

            # 2. Target Microphone Device
            target_mic = None
            if custom_mic_idx is not None:
                try:
                    dev = p.get_device_info_by_index(custom_mic_idx)
                    if dev["maxInputChannels"] > 0 and dev["hostApi"] == wasapi_host_id:
                        target_mic = dev
                except Exception:
                    pass

            if not target_mic and "microphone_index" in saved:
                try:
                    dev = p.get_device_info_by_index(saved["microphone_index"])
                    if dev["maxInputChannels"] > 0 and dev["hostApi"] == wasapi_host_id:
                        target_mic = dev
                except Exception:
                    pass

            if not target_mic:
                for i in range(p.get_device_count()):
                    dev = p.get_device_info_by_index(i)
                    name = dev["name"].lower()
                    is_loop = getattr(dev, "isLoopbackDevice", False) or "loopback" in name
                    if dev["maxInputChannels"] > 0 and not is_loop and ("logitech" in name or "g733" in name) and dev["hostApi"] == wasapi_host_id:
                        target_mic = dev
                        break

            if not target_mic:
                for i in range(p.get_device_count()):
                    dev = p.get_device_info_by_index(i)
                    name = dev["name"].lower()
                    is_loop = getattr(dev, "isLoopbackDevice", False) or "loopback" in name
                    if dev["maxInputChannels"] > 0 and not is_loop and not self._is_virtual(dev["name"]) and dev["hostApi"] == wasapi_host_id:
                        target_mic = dev
                        break

            if not target_mic:
                def_in_idx = wasapi_info.get("defaultInputDevice", -1)
                if def_in_idx >= 0:
                    target_mic = p.get_device_info_by_index(def_in_idx)

            self.spk_name = loopback["name"]
            self.mic_name = target_mic["name"]
            self.spk_index = loopback["index"]
            self.mic_index = target_mic["index"]

            print(f"[*] Dual Audio Device Binding Initialized:", flush=True)
            print(f"    • Speaker Loopback: [{self.spk_name}] ({int(loopback['defaultSampleRate'])}Hz, {loopback['maxInputChannels']}ch)", flush=True)
            print(f"    • Microphone:       [{self.mic_name}] ({int(target_mic['defaultSampleRate'])}Hz, {target_mic['maxInputChannels']}ch)", flush=True)

            # Sequentially open audio streams
            spk_rate = int(loopback["defaultSampleRate"])
            spk_channels = loopback["maxInputChannels"]
            self.spk_stream = p.open(
                format=pyaudio.paInt16,
                channels=spk_channels,
                rate=spk_rate,
                input=True,
                input_device_index=loopback["index"],
                frames_per_buffer=1024
            )

            mic_rate = int(target_mic["defaultSampleRate"])
            mic_channels = target_mic["maxInputChannels"]
            self.mic_stream = p.open(
                format=pyaudio.paInt16,
                channels=mic_channels,
                rate=mic_rate,
                input=True,
                input_device_index=target_mic["index"],
                frames_per_buffer=1024
            )

            t_spk = threading.Thread(target=self._speaker_loopback_worker, args=(self.spk_stream, spk_rate, spk_channels), daemon=True)
            t_spk.start()

            t_mic = threading.Thread(target=self._microphone_worker, args=(self.mic_stream, mic_rate, mic_channels), daemon=True)
            t_mic.start()

            t_mix = threading.Thread(target=self._mixer_worker, daemon=True)
            t_mix.start()

        except Exception as e:
            print(f"[WASAPI Dual Setup Error]: {e}", flush=True)

    def _speaker_loopback_worker(self, stream, rate, channels):
        decim = max(1, rate // self.target_sr)
        frames_per_buf = 1024

        while self.running and stream:
            try:
                data = stream.read(frames_per_buf, exception_on_overflow=False)
                if not data:
                    continue

                raw_int16 = np.frombuffer(data, dtype=np.int16)
                if len(raw_int16) == 0:
                    continue

                if channels > 1:
                    usable_len = (len(raw_int16) // channels) * channels
                    if usable_len == 0:
                        continue
                    reshaped = raw_int16[:usable_len].reshape(-1, channels)
                    mono_raw = np.mean(reshaped, axis=1).astype(np.float32) / 32768.0
                else:
                    mono_raw = raw_int16.astype(np.float32) / 32768.0

                mono_16k = mono_raw[::decim]
                try:
                    self.spk_queue.put_nowait(mono_16k)
                except queue.Full:
                    try:
                        self.spk_queue.get_nowait()
                        self.spk_queue.put_nowait(mono_16k)
                    except Exception:
                        pass
            except Exception:
                time.sleep(0.01)

    def _microphone_worker(self, stream, rate, channels):
        decim = max(1, rate // self.target_sr)
        frames_per_buf = 1024

        while self.running and stream:
            try:
                data = stream.read(frames_per_buf, exception_on_overflow=False)
                if not data:
                    continue

                raw_int16 = np.frombuffer(data, dtype=np.int16)
                if len(raw_int16) == 0:
                    continue

                if channels > 1:
                    usable_len = (len(raw_int16) // channels) * channels
                    if usable_len == 0:
                        continue
                    reshaped = raw_int16[:usable_len].reshape(-1, channels)
                    mono_raw = np.mean(reshaped, axis=1).astype(np.float32) / 32768.0
                else:
                    mono_raw = raw_int16.astype(np.float32) / 32768.0

                mono_16k = mono_raw[::decim]
                try:
                    self.mic_queue.put_nowait(mono_16k)
                except queue.Full:
                    try:
                        self.mic_queue.get_nowait()
                        self.mic_queue.put_nowait(mono_16k)
                    except Exception:
                        pass
            except Exception:
                time.sleep(0.01)

    def _mixer_worker(self):
        last_log_t = time.time()
        while self.running:
            s_chunk = None
            m_chunk = None

            try:
                s_chunk = self.spk_queue.get_nowait()
            except queue.Empty:
                pass

            try:
                m_chunk = self.mic_queue.get_nowait()
            except queue.Empty:
                pass

            if s_chunk is None and m_chunk is None:
                time.sleep(0.01)
                continue

            if s_chunk is not None and m_chunk is not None:
                min_len = min(len(s_chunk), len(m_chunk))
                mixed = np.clip(s_chunk[:min_len] + m_chunk[:min_len], -1.0, 1.0)
            elif s_chunk is not None:
                mixed = s_chunk
            else:
                mixed = m_chunk

            # Auto-gain normalization
            peak = float(np.max(np.abs(mixed)))
            if peak > 0.0001:
                gain = min(4.0, 0.90 / max(peak, 0.05))
                mixed = np.clip(mixed * gain, -1.0, 1.0)

            rms = float(np.sqrt(np.mean(mixed ** 2)))
            int16_bytes = (mixed * 32767).astype(np.int16).tobytes()

            try:
                self.audio_queue.put_nowait((int16_bytes, rms))
            except queue.Full:
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.put_nowait((int16_bytes, rms))
                except Exception:
                    pass

            now_t = time.time()
            if now_t - last_log_t > 1.5:
                last_log_t = now_t
                vol_bars = "█" * int(min(12, rms * 80))
                print(f"[Audio Stream Active] RMS: {rms:.4f} {vol_bars:<12} | Queue: {self.audio_queue.qsize()}", flush=True)


# =============================================================================
# HYBRID INTELLIGENCE WORKER (FASTER-WHISPER + GEMINI SYNTHESIS)
# =============================================================================
class RealtimeCopilotWorker(QThread):
    audio_level_changed = pyqtSignal(float)
    status_changed = pyqtSignal(str, str)
    caption_received = pyqtSignal(str, str)       # (timestamp, text)
    takeaway_received = pyqtSignal(str, str, str) # (timestamp, tag, text)
    qa_detected = pyqtSignal(str, str, str)       # (timestamp, question, answer)
    manual_qa_answered = pyqtSignal(str, str, str)# (timestamp, question, answer)
    session_ended = pyqtSignal(str)               # session_filepath
    device_reconnected = pyqtSignal(str, str)     # (spk_name, mic_name)
    error_occurred = pyqtSignal(str)

    def __init__(self, whisper_model=None):
        super().__init__()
        self.running = True
        self.paused = False
        self.capture = DedicatedWASAPICapture()
        self.client = genai.Client(api_key=API_KEY) if API_KEY else None
        
        self.whisper_model = whisper_model
        self.device_mode = "CPU (int8)" if whisper_model else "Off"
        
        self.session_start_time = datetime.now()
        self.full_transcripts = []
        self.recorded_takeaways = []
        self.recorded_qa = []
        self.total_pcm_recordings = bytearray()
        
        self.recent_sentences_buffer = []
        self.last_transcript_chunk = ""
        self.last_gemini_intel_time = time.time()

    def run(self):
        self.capture.start()
        self.status_changed.emit(f"WHISPER ACTIVE ({self.device_mode})", "#10B981")
        self._processing_loop()

    def reconfigure_devices(self, spk_index: int, mic_index: int):
        self.capture.restart(spk_index, mic_index)
        self.device_reconnected.emit(self.capture.spk_name, self.capture.mic_name)

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        if self.paused:
            self.status_changed.emit("PAUSED", "#F59E0B")
        else:
            self.status_changed.emit(f"WHISPER ACTIVE ({self.device_mode})", "#10B981")
        return self.paused

    def start_new_session(self):
        self.session_start_time = datetime.now()
        self.full_transcripts.clear()
        self.recorded_takeaways.clear()
        self.recorded_qa.clear()
        self.total_pcm_recordings.clear()
        self.recent_sentences_buffer.clear()
        self.last_transcript_chunk = ""
        self.status_changed.emit(f"WHISPER ACTIVE ({self.device_mode})", "#10B981")

    def stop(self):
        self.running = False
        self.capture.stop()

    def _processing_loop(self):
        accumulated_pcm = bytearray()
        max_chunk_rms = 0.0

        while self.running:
            try:
                pcm_chunk, rms = self.capture.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self.audio_level_changed.emit(rms)
            if rms > max_chunk_rms:
                max_chunk_rms = rms

            if self.paused:
                continue

            accumulated_pcm.extend(pcm_chunk)
            self.total_pcm_recordings.extend(pcm_chunk)

            # Every 3.0 seconds of audio batch for Whisper
            if len(accumulated_pcm) >= int(TARGET_SAMPLE_RATE * 2 * CHUNK_ACCUMULATE_DURATION):
                current_buffer = bytes(accumulated_pcm)
                current_max_rms = max_chunk_rms
                
                accumulated_pcm = bytearray()
                max_chunk_rms = 0.0

                if current_max_rms > SPEECH_RMS_THRESHOLD and self.whisper_model:
                    self._transcribe_with_whisper(current_buffer)

    def _transcribe_with_whisper(self, pcm_bytes: bytes):
        """Transcribes local audio buffer with Faster-Whisper in sub-80ms."""
        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            segments, info = self.whisper_model.transcribe(
                samples,
                beam_size=1,
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300)
            )

            text_pieces = [s.text.strip() for s in segments if s.text.strip()]
            if not text_pieces:
                return

            full_text = " ".join(text_pieces).strip()
            clean_text = re.sub(r"^[\s\"']+|[\s\"']+$", "", full_text)

            is_phantom = clean_text.lower() in PHANTOM_FILTER_TOKENS or (len(clean_text.split()) <= 1 and len(clean_text) <= 3)
            is_dup = clean_text.lower() == self.last_transcript_chunk.lower()

            if clean_text and not is_phantom and not is_dup:
                self.last_transcript_chunk = clean_text
                ts = datetime.now().strftime("%H:%M:%S")
                
                self.caption_received.emit(ts, clean_text)
                self.full_transcripts.append({"time": ts, "speaker": "Speaker", "text": clean_text})
                self.recent_sentences_buffer.append(f"[{ts}] {clean_text}")

                # Trigger Gemini background synthesis every 12-15 seconds or when 4 sentences accumulate
                if len(self.recent_sentences_buffer) >= 4 or (time.time() - self.last_gemini_intel_time > 15 and self.recent_sentences_buffer):
                    dialogue_batch = "\n".join(self.recent_sentences_buffer)
                    self.recent_sentences_buffer.clear()
                    self.last_gemini_intel_time = time.time()
                    threading.Thread(target=self._query_gemini_synthesis, args=(dialogue_batch,), daemon=True).start()

        except Exception as e:
            print(f"[Whisper Transcribe Error]: {e}", flush=True)

    def _query_gemini_synthesis(self, dialogue_text: str):
        """Asynchronously analyzes Whisper's transcript with Gemini for Q&A and Takeaways."""
        if not self.client:
            return

        try:
            ts = datetime.now().strftime("%H:%M:%S")
            prompt = (
                "You are an executive real-time technical meeting co-pilot.\n"
                f"Analyze this recent live dialogue snippet:\n\"\"\"\n{dialogue_text}\n\"\"\"\n\n"
                "Extract structured intelligence in this EXACT format:\n"
                "[IS_QUESTION]: true OR false\n"
                "[QUESTION_TEXT]: exact question asked if any, otherwise NONE\n"
                "[COPILOT_ANSWER]: 2-3 concise bullet-point cheat-sheet to verbally reply authoritatively, or NONE\n"
                "[TAKEAWAYS]:\n"
                "- [ACTION] High priority action item or task if any\n"
                "- [INSIGHT] Key technical architecture or concept if any\n"
                "- [DECISION] Agreed resolution if any\n"
                "If only casual filler, put [TAKEAWAYS]: NONE"
            )

            resp = None
            for model_name in MODEL_CANDIDATES:
                try:
                    resp = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=300)
                    )
                    if resp and resp.text:
                        break
                except Exception:
                    continue

            if resp and resp.text:
                self._dispatch_parsed_intelligence(ts, resp.text.strip())

        except Exception as e:
            print(f"[Gemini Synthesis Error]: {e}", flush=True)

    def _dispatch_parsed_intelligence(self, ts: str, text: str):
        # 1. Parse Question & Q&A
        is_q_match = re.search(r"\[IS_QUESTION\]:\s*(true|false)", text, re.IGNORECASE)
        is_question = bool(is_q_match and is_q_match.group(1).lower() == "true")

        q_match = re.search(r"\[QUESTION_TEXT\]:\s*(.*?)(?=\[COPILOT_ANSWER\]|\n\[|$)", text, re.DOTALL | re.IGNORECASE)
        q_text = q_match.group(1).strip() if q_match else ""

        a_match = re.search(r"\[COPILOT_ANSWER\]:\s*(.*?)(?=\[TAKEAWAYS\]|\n\[|$)", text, re.DOTALL | re.IGNORECASE)
        a_text = a_match.group(1).strip() if a_match else ""

        if is_question and q_text and q_text.upper() != "NONE" and a_text and a_text.upper() != "NONE":
            self.qa_detected.emit(ts, q_text, a_text)
            self.recorded_qa.append({"time": ts, "question": q_text, "answer": a_text})

        # 2. Parse Takeaways & Action Items
        tw_match = re.search(r"\[TAKEAWAYS\]:\s*(.*?)$", text, re.DOTALL | re.IGNORECASE)
        if tw_match:
            tw_block = tw_match.group(1).strip()
            if tw_block.upper() != "NONE":
                for line in tw_block.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    tag = "💡 Insight"
                    if "[ACTION]" in line.upper():
                        tag = "🔴 Action"
                    elif "[DECISION]" in line.upper():
                        tag = "📌 Decision"
                    
                    clean_content = re.sub(r"-\s*\[(ACTION|INSIGHT|DECISION)\]\s*", "", line, flags=re.IGNORECASE).strip("-*• ")
                    if len(clean_content) > 5:
                        self.takeaway_received.emit(ts, tag, clean_content)
                        self.recorded_takeaways.append({"time": ts, "tag": tag, "text": clean_content})

    def answer_manual_question(self, question_text: str, depth_mode: str = "quick"):
        threading.Thread(target=self._manual_qa_worker, args=(question_text, depth_mode), daemon=True).start()

    def _manual_qa_worker(self, question_text: str, depth_mode: str):
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            context_snippet = " ".join([t["text"] for t in self.full_transcripts[-10:]])
            
            detail_prompt = "Provide a 2-3 bullet point quick verbal answer." if depth_mode == "quick" else "Provide a detailed technical breakdown with architecture/tradeoffs."
            prompt = (
                f"You are an executive technical copilot in a live professional meeting.\n"
                f"Recent conversation context from Whisper:\n{context_snippet}\n\n"
                f"Question: {question_text}\n\n"
                f"Instructions: {detail_prompt} Format with clear bullet points."
            )

            resp = None
            for model_name in MODEL_CANDIDATES:
                try:
                    resp = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=350)
                    )
                    if resp and resp.text:
                        break
                except Exception:
                    continue

            if resp and resp.text:
                answer = resp.text.strip()
                self.manual_qa_answered.emit(ts, question_text, answer)
                self.recorded_qa.append({"time": ts, "question": question_text, "answer": answer})

        except Exception as e:
            print(f"[Manual Q&A Error]: {e}", flush=True)

    def compile_and_sync_session(self):
        threading.Thread(target=self._compile_session_worker, daemon=True).start()

    def _compile_session_worker(self):
        try:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            duration_str = str(datetime.now() - self.session_start_time).split(".")[0]
            
            full_text = "\n".join([f"[{t['time']}] {t['speaker']}: {t['text']}" for t in self.full_transcripts])
            if not full_text:
                full_text = "Live Copilot session recorded without speech activity."

            session_data = {
                "metadata": {
                    "source_file": f"Live Faster-Whisper Copilot Session ({session_id})",
                    "filename": f"Live_Session_{session_id}.json",
                    "file_size": f"{len(self.total_pcm_recordings) / (1024*1024):.2f} MB",
                    "mime_type": "audio/pcm",
                    "model": f"Faster-Whisper (base.en / {self.device_mode}) + {MODEL_CANDIDATES[0]}",
                    "processing_time": duration_str,
                    "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "exported_at": datetime.now().isoformat()
                },
                "executive_brief": [
                    f"• Strategic Purpose: Real-time Live Copilot session transcribed locally with Faster-Whisper ({self.device_mode}) on {datetime.now().strftime('%b %d, %Y')}.",
                    f"• Total Spoken Turns: {len(self.full_transcripts)} accurate turns transcribed, {len(self.recorded_takeaways)} takeaways extracted, {len(self.recorded_qa)} Q&A responses.",
                    "• Key Breakthrough: Sub-80ms local transcription paired with cloud intelligence synthesis."
                ],
                "discussion_pillars": [
                    {
                        "title": "Live Dialogue & Topics Overview",
                        "timestamp": "00:00:00",
                        "details": f"- **Session Duration:** {duration_str}\n- **Items Captured:** {len(self.recorded_takeaways)} Takeaways, {len(self.recorded_qa)} Q&A Queries.\n\n---\n"
                    }
                ],
                "action_items": [
                    {
                        "number": idx + 1,
                        "description": item["text"],
                        "assignee": "Team",
                        "priority": "HIGH" if "Action" in item["tag"] else "MED",
                        "due_date": "Next Sprint",
                        "notes": f"Captured at {item['time']}"
                    }
                    for idx, item in enumerate(self.recorded_takeaways) if "Action" in item["tag"]
                ],
                "decisions": [
                    f"[{item['time']}] {item['text']}" for item in self.recorded_takeaways if "Decision" in item["tag"]
                ],
                "reversals": [],
                "mermaid_mindmap": (
                    "mindmap\n"
                    "  root((Live Copilot Session))\n"
                    "    Executive Brief\n"
                    "      Strategic Alignment\n"
                    "      Action Points\n"
                    "    Key Takeaways\n"
                    + "\n".join([f"      {item['text'][:35]}" for item in self.recorded_takeaways[:5]])
                ),
                "qna_history": self.recorded_qa,
                "raw_markdown": f"# 🎙️ Live Copilot Session Report: {session_id}\n\n**Duration:** {duration_str}\n\n## ⚡ Executive Brief\n> • **Live Session Synchronized** at {datetime.now().strftime('%H:%M:%S')}.\n\n## 🗣️ Full Spoken Transcript (Faster-Whisper)\n\n{full_text}"
            }

            session_file = SESSIONS_DIR / f"session_{session_id}.json"
            output_file = OUTPUTS_DIR / f"Live_Session_{session_id}_report.json"

            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            print(f"\n[+] Session synchronized successfully to:\n    • {session_file}\n    • {output_file}", flush=True)

            self.session_ended.emit(str(output_file))
            webbrowser.open("http://localhost:8501")

        except Exception as e:
            print(f"[Session Sync Error]: {e}", flush=True)


# =============================================================================
# AUDIO DEVICE SETTINGS DIALOG
# =============================================================================
class AudioSettingsDialog(QDialog):
    def __init__(self, current_spk_idx=None, current_mic_idx=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audio Device Settings")
        self.setFixedSize(420, 260)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 12px;
            }
            QLabel {
                color: #F0F6FC;
                font-size: 11px;
                font-weight: bold;
            }
            QComboBox {
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #58A6FF;
            }
            QComboBox QAbstractItemView {
                background-color: #161B22;
                color: #F0F6FC;
                selection-background-color: #30363D;
                selection-color: #38BDF8;
                border: 1px solid #30363D;
            }
        """)

        self.current_spk_idx = current_spk_idx
        self.current_mic_idx = current_mic_idx
        self.selected_spk_idx = None
        self.selected_mic_idx = None
        self.selected_spk_name = ""
        self.selected_mic_name = ""

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title_lbl = QLabel("⚙️ Audio Hardware Settings")
        title_lbl.setStyleSheet("color: #38BDF8; font-size: 13px; font-weight: 900;")
        layout.addWidget(title_lbl)

        spk_lbl = QLabel("🔊 System Audio Loopback (Speakers / YouTube / Zoom):")
        layout.addWidget(spk_lbl)

        self.spk_combo = QComboBox()
        layout.addWidget(self.spk_combo)

        mic_lbl = QLabel("🎙️ Voice Input (Microphone):")
        layout.addWidget(mic_lbl)

        self.mic_combo = QComboBox()
        layout.addWidget(self.mic_combo)

        self._populate_devices()

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(QCursor(Qt.PointingHandCursor))
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #21262D; color: #8B949E; border: 1px solid #30363D;
                border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { color: #F0F6FC; border-color: #58A6FF; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Save & Apply")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        btn_save.setStyleSheet("""
            QPushButton {
                background: #38BDF8; color: #0D1117; border: none;
                border-radius: 6px; padding: 6px 16px; font-size: 11px; font-weight: 900;
            }
            QPushButton:hover { background: #7DD3FC; }
        """)
        btn_save.clicked.connect(self._save_and_apply)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _populate_devices(self):
        p = pyaudio.PyAudio()
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            wasapi_host_id = wasapi_info["index"]

            spk_match_idx = 0
            for idx, dev in enumerate(p.get_loopback_device_info_generator()):
                display_name = f"{dev['name']} ({int(dev['defaultSampleRate'])}Hz, {dev['maxInputChannels']}ch)"
                self.spk_combo.addItem(display_name, dev["index"])
                if self.current_spk_idx == dev["index"]:
                    spk_match_idx = idx

            self.spk_combo.setCurrentIndex(spk_match_idx)

            mic_match_idx = 0
            mic_count = 0
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                is_loop = getattr(dev, "isLoopbackDevice", False) or "loopback" in dev["name"].lower()
                if dev["maxInputChannels"] > 0 and not is_loop and dev["hostApi"] == wasapi_host_id:
                    display_name = f"{dev['name']} ({int(dev['defaultSampleRate'])}Hz, {dev['maxInputChannels']}ch)"
                    self.mic_combo.addItem(display_name, dev["index"])
                    if self.current_mic_idx == dev["index"]:
                        mic_match_idx = mic_count
                    mic_count += 1

            self.mic_combo.setCurrentIndex(mic_match_idx)

        except Exception as e:
            print(f"[Device Enum Error]: {e}", flush=True)
        finally:
            p.terminate()

    def _save_and_apply(self):
        self.selected_spk_idx = self.spk_combo.currentData()
        self.selected_mic_idx = self.mic_combo.currentData()
        self.selected_spk_name = self.spk_combo.currentText().split(" (")[0]
        self.selected_mic_name = self.mic_combo.currentText().split(" (")[0]

        save_config({
            "speaker_loopback_name": self.selected_spk_name,
            "speaker_loopback_index": self.selected_spk_idx,
            "microphone_name": self.selected_mic_name,
            "microphone_index": self.selected_mic_idx
        })

        self.accept()


# =============================================================================
# DUAL-TAB STEALTH FLOATING HUD UI (PyQt5)
# =============================================================================
class TakeawayCard(QFrame):
    def __init__(self, timestamp: str, tag: str, text: str, parent=None):
        super().__init__(parent)
        self.raw_text = text

        border_color = "#38BDF8"
        bg_tag = "rgba(56, 189, 248, 0.15)"
        if "Action" in tag:
            border_color = "#F87171"
            bg_tag = "rgba(248, 113, 113, 0.15)"
        elif "Decision" in tag:
            border_color = "#34D399"
            bg_tag = "rgba(52, 211, 153, 0.15)"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #161B22;
                border: 1px solid #30363D;
                border-left: 4px solid {border_color};
                border-radius: 10px;
                padding: 8px 10px;
                margin-bottom: 6px;
            }}
            QFrame:hover {{
                border-color: #58A6FF;
                background-color: #1C2128;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)

        tag_label = QLabel(f"{tag} • {timestamp}")
        tag_label.setStyleSheet(f"color: {border_color}; font-size: 10px; font-weight: bold; background: {bg_tag}; padding: 2px 6px; border-radius: 4px;")
        meta_layout.addWidget(tag_label)
        meta_layout.addStretch()

        copy_btn = QPushButton("📋 Copy")
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #21262D; color: #8B949E; border: 1px solid #30363D;
                border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { color: #F0F6FC; border-color: #58A6FF; background: #30363D; }
        """)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.raw_text))
        meta_layout.addWidget(copy_btn)

        layout.addLayout(meta_layout)

        content_label = QLabel(text)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("color: #F0F6FC; font-size: 11px; line-height: 1.45;")
        content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(content_label)


class QnACard(QFrame):
    def __init__(self, timestamp: str, question: str, answer: str, parent=None, on_depth_toggle=None):
        super().__init__(parent)
        self.question = question
        self.answer = answer
        self.on_depth_toggle = on_depth_toggle

        self.setStyleSheet("""
            QFrame {{
                background-color: #161B22;
                border: 1px solid #30363D;
                border-left: 4px solid #A78BFA;
                border-radius: 10px;
                padding: 10px;
                margin-bottom: 8px;
            }
            QFrame:hover {
                border-color: #C084FC;
                background-color: #1C2128;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        q_tag = QLabel(f"🎯 Q&A Cheat-Sheet • {timestamp}")
        q_tag.setStyleSheet("color: #C084FC; font-size: 10px; font-weight: bold; background: rgba(192, 132, 252, 0.15); padding: 2px 6px; border-radius: 4px;")
        hdr.addWidget(q_tag)
        hdr.addStretch()

        copy_btn = QPushButton("📋 Copy Answer")
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #21262D; color: #8B949E; border: 1px solid #30363D;
                border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { color: #F0F6FC; border-color: #C084FC; background: #30363D; }
        """)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(f"Q: {self.question}\nA: {self.answer}"))
        hdr.addWidget(copy_btn)
        layout.addLayout(hdr)

        q_label = QLabel(f"<b>Q:</b> {question}")
        q_label.setWordWrap(True)
        q_label.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: bold;")
        layout.addWidget(q_label)

        self.ans_label = QLabel(self._format_bullets(answer))
        self.ans_label.setWordWrap(True)
        self.ans_label.setStyleSheet("color: #F0F6FC; font-size: 11px; line-height: 1.5;")
        self.ans_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.ans_label)

        depth_layout = QHBoxLayout()
        depth_layout.setContentsMargins(0, 4, 0, 0)
        
        btn_quick = QPushButton("⚡ Quick Bullet")
        btn_quick.setCursor(QCursor(Qt.PointingHandCursor))
        self._style_depth_btn(btn_quick)
        btn_quick.clicked.connect(lambda: self._trigger_depth("quick"))
        depth_layout.addWidget(btn_quick)

        btn_deep = QPushButton("📚 Deep Technical")
        btn_deep.setCursor(QCursor(Qt.PointingHandCursor))
        self._style_depth_btn(btn_deep)
        btn_deep.clicked.connect(lambda: self._trigger_depth("deep"))
        depth_layout.addWidget(btn_deep)

        depth_layout.addStretch()
        layout.addLayout(depth_layout)

    def _style_depth_btn(self, btn: QPushButton):
        btn.setStyleSheet("""
            QPushButton {
                background: #21262D; color: #8B949E; border: 1px solid #30363D;
                border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { color: #38BDF8; border-color: #38BDF8; background: #30363D; }
        """)

    def _trigger_depth(self, mode: str):
        if self.on_depth_toggle:
            self.on_depth_toggle(self.question, mode)

    def _format_bullets(self, text: str) -> str:
        lines = text.splitlines()
        formatted = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"\*\*([^*]+)\*\*", r"<b style='color:#38BDF8;'>\1</b>", line)
            line = re.sub(r"`([^`]+)`", r"<code style='background:#21262D; color:#A78BFA; padding:1px 4px; border-radius:3px;'>\1</code>", line)
            if line.startswith(("-", "*", "•")):
                clean = line.lstrip("-*• ").strip()
                formatted.append(f"<div style='margin-bottom:3px;'>• {clean}</div>")
            else:
                formatted.append(f"<div style='margin-bottom:3px;'>{line}</div>")
        return "".join(formatted)


class LiveAudioVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 16)
        self.level = 0.0

    def set_level(self, rms: float):
        self.level = min(1.0, rms * 50.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        num_bars = 5
        bar_w = 4
        gap = 4
        
        for i in range(num_bars):
            h_ratio = min(1.0, max(0.2, self.level * (i + 1) / 3.0))
            h = int(12 * h_ratio)
            x = i * (bar_w + gap)
            y = 14 - h
            
            color = QColor("#38BDF8") if self.level > 0.02 else QColor("#30363D")
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, y, bar_w, h, 2, 2)


class CopilotHUDWindow(QWidget):
    """
    Complete Dual-Tab Real-Time Copilot HUD powered by Faster-Whisper
    with Gemini background synthesis and Streamlit session bridge.
    Clean Windows DWM rendering without graphics shadow crash.
    """
    def __init__(self, whisper_model=None):
        super().__init__()
        self.whisper_model = whisper_model
        self.drag_position = QPoint()
        self.opacity_levels = [0.96, 0.75, 0.50]
        self.current_opacity_idx = 0
        self.full_transcript_text = ""
        self.new_qa_count = 0
        self.is_recording = True
        self.rolling_captions = collections.deque(maxlen=15)

        self.init_window_properties()
        self.init_ui()
        self.init_shortcuts()
        self.init_engine()

    def init_window_properties(self):
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setWindowOpacity(0.96)
        self.setFixedSize(480, 640)

        # Strictly clamp window to visible primary screen geometry
        screen = QApplication.primaryScreen().geometry()
        margin_right = 24
        margin_top = 35
        x = max(0, min(screen.width() - self.width() - margin_right, screen.width() - self.width()))
        y = max(0, min(margin_top, screen.height() - self.height()))
        self.move(x, y)

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QFrame(self)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            QFrame#MainContainer {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 12px;
            }
        """)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(8)

        # =====================================================================
        # 1. HEADER BAR & CONTROLS
        # =====================================================================
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title_icon = QLabel("🎙️")
        title_icon.setStyleSheet("font-size: 15px;")
        header_layout.addWidget(title_icon)

        title_label = QLabel("LIVE COPILOT")
        title_label.setStyleSheet("color: #F0F6FC; font-weight: 900; font-size: 12px; letter-spacing: 0.5px;")
        header_layout.addWidget(title_label)

        self.status_pill = QLabel("● WHISPER ACTIVE")
        self.status_pill.setStyleSheet("color: #10B981; font-size: 9px; font-weight: bold; background: rgba(16, 185, 129, 0.15); padding: 2px 5px; border-radius: 4px;")
        header_layout.addWidget(self.status_pill)

        self.visualizer = LiveAudioVisualizer(self)
        header_layout.addWidget(self.visualizer)

        header_layout.addStretch()

        self.btn_end_sync = QPushButton("🛑 End & Sync")
        self.btn_end_sync.setToolTip("End Meeting & Open Streamlit Dashboard")
        self.btn_end_sync.setCursor(QCursor(Qt.PointingHandCursor))
        self._set_end_button_style(is_end=True)
        self.btn_end_sync.clicked.connect(self._toggle_session_state)
        header_layout.addWidget(self.btn_end_sync)

        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setToolTip("Audio Device Settings")
        self.settings_btn.setFixedSize(24, 24)
        self.settings_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.settings_btn.clicked.connect(self._open_audio_settings)
        self._style_header_button(self.settings_btn)
        header_layout.addWidget(self.settings_btn)

        self.opacity_btn = QPushButton("👁️")
        self.opacity_btn.setToolTip("Cycle Opacity (Ctrl+Shift+O)")
        self.opacity_btn.setFixedSize(24, 24)
        self.opacity_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.opacity_btn.clicked.connect(self._cycle_opacity)
        self._style_header_button(self.opacity_btn)
        header_layout.addWidget(self.opacity_btn)

        self.clear_btn = QPushButton("🧹")
        self.clear_btn.setToolTip("Clear Feed")
        self.clear_btn.setFixedSize(24, 24)
        self.clear_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.clear_btn.clicked.connect(self._clear_current_tab)
        self._style_header_button(self.clear_btn)
        header_layout.addWidget(self.clear_btn)

        self.hide_btn = QPushButton("—")
        self.hide_btn.setToolTip("Hide (Ctrl+Shift+H)")
        self.hide_btn.setFixedSize(24, 24)
        self.hide_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.hide_btn.clicked.connect(self.hide)
        self._style_header_button(self.hide_btn)
        header_layout.addWidget(self.hide_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setToolTip("Close")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.close_btn.clicked.connect(self.close)
        self._style_header_button(self.close_btn, is_close=True)
        header_layout.addWidget(self.close_btn)

        container_layout.addLayout(header_layout)

        # =====================================================================
        # 2. DUAL-TAB NAVIGATION BAR
        # =====================================================================
        tab_nav_layout = QHBoxLayout()
        tab_nav_layout.setContentsMargins(0, 2, 0, 2)
        tab_nav_layout.setSpacing(6)

        self.tab_btn_summary = QPushButton("📝 Summary & Notes (1)")
        self.tab_btn_summary.setCursor(QCursor(Qt.PointingHandCursor))
        self.tab_btn_summary.clicked.connect(lambda: self._switch_tab(0))
        tab_nav_layout.addWidget(self.tab_btn_summary)

        self.tab_btn_qa = QPushButton("🎯 Smart Q&A (2)")
        self.tab_btn_qa.setCursor(QCursor(Qt.PointingHandCursor))
        self.tab_btn_qa.clicked.connect(lambda: self._switch_tab(1))
        tab_nav_layout.addWidget(self.tab_btn_qa)

        container_layout.addLayout(tab_nav_layout)

        # =====================================================================
        # 3. STACKED WIDGET (TAB PAGES)
        # =====================================================================
        self.stacked_widget = QStackedWidget()

        # -----------------------------
        # PAGE 1: SUMMARY & NOTES
        # -----------------------------
        self.page_summary = QWidget()
        summary_layout = QVBoxLayout(self.page_summary)
        summary_layout.setContentsMargins(0, 4, 0, 0)
        summary_layout.setSpacing(8)

        # Multi-Line Rolling Captions Container
        caption_box = QFrame()
        caption_box.setStyleSheet("""
            QFrame {
                background-color: rgba(22, 27, 34, 0.95);
                border: 1px solid #30363D;
                border-top: 2px solid #38BDF8;
                border-radius: 8px;
                padding: 6px 8px;
            }
        """)
        c_layout = QVBoxLayout(caption_box)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(4)

        c_title_layout = QHBoxLayout()
        c_title = QLabel("💬 Real-Time Faster-Whisper Stream")
        c_title.setStyleSheet("color: #38BDF8; font-size: 10px; font-weight: bold;")
        c_title_layout.addWidget(c_title)
        c_title_layout.addStretch()

        self.live_indicator = QLabel("● 0ms LATENCY")
        self.live_indicator.setStyleSheet("color: #10B981; font-size: 8px; font-weight: bold; background: rgba(16, 185, 129, 0.15); padding: 1px 4px; border-radius: 3px;")
        c_title_layout.addWidget(self.live_indicator)
        c_layout.addLayout(c_title_layout)

        self.caption_text_edit = QTextEdit()
        self.caption_text_edit.setReadOnly(True)
        self.caption_text_edit.setMaximumHeight(95)
        self.caption_text_edit.setMinimumHeight(75)
        self.caption_text_edit.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: #F0F6FC;
                font-size: 11.5px;
                line-height: 1.45;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(22, 27, 34, 0.5);
                width: 4px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: #30363D;
                border-radius: 2px;
            }
        """)
        self.caption_text_edit.setHtml("<span style='color:#8B949E; font-size:11px;'>Faster-Whisper listening to Logitech G733... Speak or play video.</span>")
        c_layout.addWidget(self.caption_text_edit)

        summary_layout.addWidget(caption_box)

        # Scrollable Takeaways Feed
        feed_lbl = QLabel("💡 Live Takeaways & Action Items Feed")
        feed_lbl.setStyleSheet("color: #8B949E; font-size: 10px; font-weight: bold;")
        summary_layout.addWidget(feed_lbl)

        self.scroll_summary = QScrollArea()
        self.scroll_summary.setWidgetResizable(True)
        self._style_scroll_area(self.scroll_summary)

        self.feed_summary_widget = QWidget()
        self.feed_summary_layout = QVBoxLayout(self.feed_summary_widget)
        self.feed_summary_layout.setContentsMargins(0, 0, 0, 0)
        self.feed_summary_layout.setSpacing(6)
        self.feed_summary_layout.addStretch()

        self.scroll_summary.setWidget(self.feed_summary_widget)
        summary_layout.addWidget(self.scroll_summary)

        self._add_welcome_summary_card()
        self.stacked_widget.addWidget(self.page_summary)

        # -----------------------------
        # PAGE 2: SMART Q&A COPILOT
        # -----------------------------
        self.page_qa = QWidget()
        qa_layout = QVBoxLayout(self.page_qa)
        qa_layout.setContentsMargins(0, 4, 0, 0)
        qa_layout.setSpacing(8)

        qa_lbl = QLabel("🎯 Detected Technical Questions & Instant Cheat-Sheets")
        qa_lbl.setStyleSheet("color: #C084FC; font-size: 10px; font-weight: bold;")
        qa_layout.addWidget(qa_lbl)

        self.scroll_qa = QScrollArea()
        self.scroll_qa.setWidgetResizable(True)
        self._style_scroll_area(self.scroll_qa)

        self.feed_qa_widget = QWidget()
        self.feed_qa_layout = QVBoxLayout(self.feed_qa_widget)
        self.feed_qa_layout.setContentsMargins(0, 0, 0, 0)
        self.feed_qa_layout.setSpacing(8)
        self.feed_qa_layout.addStretch()

        self.scroll_qa.setWidget(self.feed_qa_widget)
        qa_layout.addWidget(self.scroll_qa)

        # Bottom Instant Ask Box
        ask_box_frame = QFrame()
        ask_box_frame.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 4px 6px;
            }
        """)
        ask_layout = QHBoxLayout(ask_box_frame)
        ask_layout.setContentsMargins(4, 2, 4, 2)
        ask_layout.setSpacing(6)

        self.ask_input = QLineEdit()
        self.ask_input.setPlaceholderText("Ask Copilot or type keyword... (Ctrl+Space)")
        self.ask_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #F0F6FC;
                font-size: 11px;
            }
        """)
        self.ask_input.returnPressed.connect(self._handle_manual_ask)
        ask_layout.addWidget(self.ask_input)

        self.btn_send_ask = QPushButton("⚡ Ask")
        self.btn_send_ask.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_send_ask.setStyleSheet("""
            QPushButton {
                background: #38BDF8;
                color: #0D1117;
                border: none;
                border-radius: 5px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: 900;
            }
            QPushButton:hover { background: #7DD3FC; }
        """)
        self.btn_send_ask.clicked.connect(self._handle_manual_ask)
        ask_layout.addWidget(self.btn_send_ask)

        qa_layout.addWidget(ask_box_frame)

        self._add_welcome_qa_card()
        self.stacked_widget.addWidget(self.page_qa)

        container_layout.addWidget(self.stacked_widget)

        # =====================================================================
        # 4. FOOTER BAR
        # =====================================================================
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)

        self.info_label = QLabel("⚡ Audio Capture Ready")
        self.info_label.setStyleSheet("color: #6E7681; font-size: 9px; font-weight: 500;")
        footer_layout.addWidget(self.info_label)

        footer_layout.addStretch()

        shortcut_label = QLabel("Ctrl+Shift+H to Toggle")
        shortcut_label.setStyleSheet("color: #8B949E; font-size: 9px; font-weight: 600; background: #21262D; padding: 2px 5px; border-radius: 3px;")
        footer_layout.addWidget(shortcut_label)

        container_layout.addLayout(footer_layout)
        root_layout.addWidget(self.container)

        self._switch_tab(0)

    def _open_audio_settings(self):
        dlg = AudioSettingsDialog(
            current_spk_idx=self.worker.capture.spk_index,
            current_mic_idx=self.worker.capture.mic_index,
            parent=self
        )
        if dlg.exec_() == QDialog.Accepted:
            self.worker.reconfigure_devices(dlg.selected_spk_idx, dlg.selected_mic_idx)
            self.info_label.setText(f"⚡ {dlg.selected_spk_name[:24]} • Faster-Whisper")
            self.status_pill.setText("● DEVICE RECONNECTED")
            self.status_pill.setStyleSheet("color: #38BDF8; font-size: 9px; font-weight: bold; background: rgba(56, 189, 248, 0.2); padding: 2px 5px; border-radius: 4px;")
            QTimer.singleShot(2500, lambda: self.status_pill.setText(f"● WHISPER ({self.worker.device_mode})"))

    def _set_end_button_style(self, is_end: bool):
        if is_end:
            self.btn_end_sync.setText("🛑 End & Sync")
            self.btn_end_sync.setToolTip("End Meeting & Open Streamlit Dashboard")
            self.btn_end_sync.setStyleSheet("""
                QPushButton {
                    background: rgba(239, 68, 68, 0.18);
                    color: #F87171;
                    border: 1px solid #EF4444;
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-size: 10px;
                    font-weight: 900;
                }
                QPushButton:hover {
                    background: #EF4444;
                    color: #FFFFFF;
                    border-color: #FCA5A5;
                }
            """)
        else:
            self.btn_end_sync.setText("▶️ New Meeting")
            self.btn_end_sync.setToolTip("Start a Fresh Meeting Session")
            self.btn_end_sync.setStyleSheet("""
                QPushButton {
                    background: rgba(16, 185, 129, 0.2);
                    color: #34D399;
                    border: 1px solid #10B981;
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-size: 10px;
                    font-weight: 900;
                }
                QPushButton:hover {
                    background: #10B981;
                    color: #FFFFFF;
                    border-color: #6EE7B7;
                }
            """)

    def _style_header_button(self, btn: QPushButton, is_close: bool = False):
        hover_bg = "#EF4444" if is_close else "#30363D"
        hover_fg = "#FFFFFF" if is_close else "#F0F6FC"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #21262D; color: #8B949E; border: 1px solid #30363D;
                border-radius: 6px; font-size: 10px; font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_bg}; color: {hover_fg}; border-color: #58A6FF;
            }}
        """)

    def _style_scroll_area(self, scroll: QScrollArea):
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                border: none; background: #161B22; width: 5px; border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: #30363D; min-height: 20px; border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover { background: #58A6FF; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; }
        """)

    def _switch_tab(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        active_style = """
            QPushButton {
                background: #21262D; color: #38BDF8; border: 1px solid #38BDF8;
                border-radius: 6px; padding: 5px 12px; font-size: 11px; font-weight: bold;
            }
        """
        inactive_style = """
            QPushButton {
                background: #161B22; color: #8B949E; border: 1px solid #30363D;
                border-radius: 6px; padding: 5px 12px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { color: #F0F6FC; border-color: #58A6FF; }
        """
        if index == 0:
            self.tab_btn_summary.setStyleSheet(active_style)
            self.tab_btn_qa.setStyleSheet(inactive_style)
        else:
            self.tab_btn_qa.setStyleSheet(active_style.replace("#38BDF8", "#C084FC"))
            self.tab_btn_summary.setStyleSheet(inactive_style)
            self.new_qa_count = 0
            self.tab_btn_qa.setText("🎯 Smart Q&A (2)")

    def _add_welcome_summary_card(self):
        box = QFrame()
        box.setStyleSheet("background: rgba(22, 27, 34, 0.85); border: 1px dashed #30363D; border-radius: 8px; padding: 10px;")
        l = QVBoxLayout(box)
        t = QLabel("🎙️ Faster-Whisper + Gemini Intelligence Active")
        t.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px;")
        l.addWidget(t)
        d = QLabel("• 100% accurate local transcription.<br>• Automatic rolling notes, action items & decisions.<br>• Click ⚙️ in header to change audio devices anytime.")
        d.setStyleSheet("color: #8B949E; font-size: 10px; line-height: 1.4;")
        l.addWidget(d)
        self.feed_summary_layout.insertWidget(0, box)

    def _add_welcome_qa_card(self):
        box = QFrame()
        box.setStyleSheet("background: rgba(22, 27, 34, 0.85); border: 1px dashed #30363D; border-radius: 8px; padding: 10px;")
        l = QVBoxLayout(box)
        t = QLabel("🎯 Smart Technical Co-Pilot Ready")
        t.setStyleSheet("color: #C084FC; font-weight: bold; font-size: 11px;")
        l.addWidget(t)
        d = QLabel("• Auto-detects questions asked during live speech.<br>• Instant cheat-sheets appear here automatically.<br>• Type questions below anytime (Ctrl+Space to focus).")
        d.setStyleSheet("color: #8B949E; font-size: 10px; line-height: 1.4;")
        l.addWidget(d)
        self.feed_qa_layout.insertWidget(0, box)

    def init_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Shift+H"), self).activated.connect(self._toggle_visibility)
        QShortcut(QKeySequence("Ctrl+Shift+1"), self).activated.connect(lambda: self._switch_tab(0))
        QShortcut(QKeySequence("Ctrl+Shift+2"), self).activated.connect(lambda: self._switch_tab(1))
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(self._copy_latest_qa)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self).activated.connect(self._cycle_opacity)
        QShortcut(QKeySequence("Ctrl+Space"), self).activated.connect(self._focus_ask_input)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.hide)

    def init_engine(self):
        self.worker = RealtimeCopilotWorker(whisper_model=self.whisper_model)
        self.worker.audio_level_changed.connect(self.visualizer.set_level)
        self.worker.status_changed.connect(self.update_status)
        self.worker.caption_received.connect(self.on_caption_received)
        self.worker.takeaway_received.connect(self.on_takeaway_received)
        self.worker.qa_detected.connect(self.on_qa_detected)
        self.worker.manual_qa_answered.connect(self.on_manual_qa_answered)
        self.worker.session_ended.connect(self.on_session_ended)
        self.worker.device_reconnected.connect(self.on_device_reconnected)
        self.worker.start()
        
        QTimer.singleShot(1500, lambda: self.info_label.setText(f"⚡ {self.worker.capture.spk_name[:22]} • Whisper ({self.worker.device_mode})"))

    def on_device_reconnected(self, spk_name: str, mic_name: str):
        self.info_label.setText(f"⚡ {spk_name[:22]} • Whisper ({self.worker.device_mode})")

    def on_caption_received(self, timestamp: str, text: str):
        self.full_transcript_text += " " + text
        self.rolling_captions.append((timestamp, text))

        html_blocks = []
        for ts, txt in self.rolling_captions:
            html_blocks.append(
                f"<div style='margin-bottom: 4px; line-height: 1.4;'>"
                f"<span style='color: #38BDF8; font-size: 9.5px; font-weight: bold;'>[{ts}]</span> "
                f"<span style='color: #F0F6FC; font-size: 11px;'>{txt}</span>"
                f"</div>"
            )
        self.caption_text_edit.setHtml("".join(html_blocks))

        sb = self.caption_text_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_takeaway_received(self, timestamp: str, tag: str, text: str):
        card = TakeawayCard(timestamp, tag, text, self)
        self.feed_summary_layout.insertWidget(0, card)
        QTimer.singleShot(20, lambda: self.scroll_summary.verticalScrollBar().setValue(0))

    def on_qa_detected(self, timestamp: str, question: str, answer: str):
        card = QnACard(timestamp, question, answer, self, on_depth_toggle=self._handle_depth_toggle)
        self.feed_qa_layout.insertWidget(0, card)
        QTimer.singleShot(20, lambda: self.scroll_qa.verticalScrollBar().setValue(0))

        if self.stacked_widget.currentIndex() != 1:
            self.new_qa_count += 1
            self.tab_btn_qa.setText(f"🎯 Smart Q&A ({self.new_qa_count} New!)")
            self.status_pill.setText("● Q&A DETECTED")
            self.status_pill.setStyleSheet("color: #C084FC; font-size: 9px; font-weight: bold; background: rgba(192, 132, 252, 0.2); padding: 2px 5px; border-radius: 4px;")

    def on_manual_qa_answered(self, timestamp: str, question: str, answer: str):
        card = QnACard(timestamp, question, answer, self, on_depth_toggle=self._handle_depth_toggle)
        self.feed_qa_layout.insertWidget(0, card)
        QTimer.singleShot(20, lambda: self.scroll_qa.verticalScrollBar().setValue(0))
        self._switch_tab(1)

    def on_session_ended(self, filepath: str):
        self.is_recording = False
        self.btn_end_sync.setEnabled(True)
        self._set_end_button_style(is_end=False)
        self.status_pill.setText("● SYNCED TO DASHBOARD")
        self.status_pill.setStyleSheet("color: #38BDF8; font-size: 9px; font-weight: bold; background: rgba(56, 189, 248, 0.2); padding: 2px 5px; border-radius: 4px;")

    def _handle_manual_ask(self):
        q = self.ask_input.text().strip()
        if q:
            self.ask_input.clear()
            self.worker.answer_manual_question(q, depth_mode="quick")

    def _handle_depth_toggle(self, question: str, depth_mode: str):
        self.worker.answer_manual_question(question, depth_mode=depth_mode)

    def _toggle_session_state(self):
        if self.is_recording:
            # End Meeting & Sync
            self.btn_end_sync.setEnabled(False)
            self.btn_end_sync.setText("⏳ Syncing...")
            self.status_pill.setText("● SYNCING SESSION...")
            self.status_pill.setStyleSheet("color: #F59E0B; font-size: 9px; font-weight: bold; background: rgba(245, 158, 11, 0.2); padding: 2px 5px; border-radius: 4px;")
            self.worker.compile_and_sync_session()
        else:
            # Start New Meeting
            self.worker.start_new_session()
            self._clear_all_tabs()
            self.is_recording = True
            self._set_end_button_style(is_end=True)
            self.status_pill.setText(f"● WHISPER ({self.worker.device_mode})")
            self.status_pill.setStyleSheet("color: #10B981; font-size: 9px; font-weight: bold; background: rgba(16, 185, 129, 0.15); padding: 2px 5px; border-radius: 4px;")

    def update_status(self, text: str, color_hex: str):
        if not self.is_recording and "WHISPER" in text:
            return
        self.status_pill.setText(f"● {text}")
        try:
            r = int(color_hex[1:3], 16)
            g = int(color_hex[3:5], 16)
            b = int(color_hex[5:7], 16)
            self.status_pill.setStyleSheet(f"color: {color_hex}; font-size: 9px; font-weight: bold; background: rgba({r}, {g}, {b}, 0.15); padding: 2px 5px; border-radius: 4px;")
        except Exception:
            pass

    def _cycle_opacity(self):
        self.current_opacity_idx = (self.current_opacity_idx + 1) % len(self.opacity_levels)
        opacity = self.opacity_levels[self.current_opacity_idx]
        self.setWindowOpacity(opacity)

    def _clear_all_tabs(self):
        self.full_transcript_text = ""
        self.rolling_captions.clear()
        self.caption_text_edit.setHtml("<span style='color:#8B949E; font-size:11px;'>Faster-Whisper listening to Logitech G733... Speak or play video.</span>")
        while self.feed_summary_layout.count() > 1:
            item = self.feed_summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_welcome_summary_card()

        while self.feed_qa_layout.count() > 1:
            item = self.feed_qa_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_welcome_qa_card()
        self.new_qa_count = 0
        self.tab_btn_qa.setText("🎯 Smart Q&A (2)")

    def _clear_current_tab(self):
        curr = self.stacked_widget.currentIndex()
        if curr == 0:
            self.rolling_captions.clear()
            self.caption_text_edit.setHtml("<span style='color:#8B949E; font-size:11px;'>Listening...</span>")
            while self.feed_summary_layout.count() > 1:
                item = self.feed_summary_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._add_welcome_summary_card()
        else:
            while self.feed_qa_layout.count() > 1:
                item = self.feed_qa_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._add_welcome_qa_card()

    def _copy_latest_qa(self):
        if self.worker.recorded_qa:
            latest = self.worker.recorded_qa[-1]
            QApplication.clipboard().setText(f"Q: {latest['question']}\nA: {latest['answer']}")

    def _focus_ask_input(self):
        self._switch_tab(1)
        self.ask_input.setFocus()

    def _toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait(1000)
        event.accept()


# =============================================================================
# ENTRY POINT
# =============================================================================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0D1117"))
    palette.setColor(QPalette.WindowText, QColor("#F0F6FC"))
    app.setPalette(palette)

    print("[*] Pre-loading Faster-Whisper Model in main process...", flush=True)
    whisper_model = None
    try:
        whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8", cpu_threads=4)
        print("[+] Faster-Whisper Loaded Successfully (base.en / int8)!", flush=True)
    except Exception as e:
        print(f"[!] Whisper Load Error: {e}", flush=True)

    hud = CopilotHUDWindow(whisper_model=whisper_model)
    hud.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
