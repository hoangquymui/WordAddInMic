import os
import re
import time
import asyncio
import threading
import warnings
from collections import deque
from datetime import datetime

import numpy as np
import torch
import sherpa_onnx
from .number_normalizer import normalize_vietnamese_numbers
from .codeMode import apply_code_mode
from fastapi import WebSocket


# =========================
# DEBUG LOG
# =========================
DEBUG = False
LOG_PCM_EVERY = 10


def log(stage, msg=""):
    if not DEBUG:
        return

    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{now}] [{stage:<12}] {msg}")


# =========================
# PATH CONFIG
# =========================
import sys

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_ROOT = os.path.dirname(MODEL_DIR)

SILERO_DIR = os.path.join(
    MODELS_ROOT,
    "vad",
)

def find_sherpa_onnx_paths(base_dir: str):
    search_dirs = [
        base_dir,
        os.path.join(base_dir, "sherpa-onnx-zipformer"),
    ]
    for candidate in os.listdir(base_dir):
        full = os.path.join(base_dir, candidate)
        if os.path.isdir(full):
            search_dirs.append(full)

    encoder = decoder = joiner = tokens = None
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        files = os.listdir(d)
        for f in files:
            path = os.path.join(d, f)
            if f == "tokens.txt":
                tokens = path
            elif f.startswith("encoder") and f.endswith(".onnx"):
                encoder = path
            elif f.startswith("decoder") and f.endswith(".onnx"):
                decoder = path
            elif f.startswith("joiner") and f.endswith(".onnx"):
                joiner = path

        if encoder and decoder and joiner and tokens:
            return encoder, decoder, joiner, tokens

    raise FileNotFoundError(f"Không tìm đủ file ONNX trong {base_dir}")

ENCODER_PATH, DECODER_PATH, JOINER_PATH, TOKENS_PATH = find_sherpa_onnx_paths(MODEL_DIR)


# =========================
# AUDIO CONFIG
# =========================
SAMPLE_RATE = 16000

MIN_DECODE_SECONDS = 0.3
MAX_WINDOW_SECONDS = 6.0
STEP_SECONDS = 0.25
RING_BUFFER_SECONDS = 12

MIN_DECODE_SAMPLES = int(SAMPLE_RATE * MIN_DECODE_SECONDS)
MAX_WINDOW_SAMPLES = int(SAMPLE_RATE * MAX_WINDOW_SECONDS)
RING_BUFFER_SAMPLES = int(SAMPLE_RATE * RING_BUFFER_SECONDS)

SILENCE_SECONDS_TO_COMMIT = 0.7

VAD_THRESHOLD = 0.35
RMS_FALLBACK_THRESHOLD = 0.02
NOISE_FILLER_WORDS = {"ừ", "à", "uh", "ừm", "ơ", "ư", "hà", "hử", "ê", "ha", "hm", "hmm"}

MIN_TEXT_LENGTH = 1


# =========================
# TEXT UTILS
# =========================
def clean_text(text: str) -> str:
    text = str(text).strip().lower()

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r",{2,}", ",", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r"([,.!?])([^\s])", r"\1 \2", text)

    text = re.sub(r"[.,!?;:]+$", "", text)

    return text.strip()


def is_bad_text(text: str) -> bool:
    clean = text.lower().strip()
    if len(clean) < MIN_TEXT_LENGTH:
        return True
    if clean in NOISE_FILLER_WORDS:
        return True
    return False


# =========================
# AUDIO UTILS
# =========================
def pcm_bytes_to_float32(audio_bytes: bytes) -> np.ndarray:
    audio = np.frombuffer(audio_bytes, dtype=np.int16)

    if audio.size == 0:
        return np.array([], dtype=np.float32)

    return audio.astype(np.float32) / 32768.0


def rms_value(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0

    return float(np.sqrt(np.mean(audio ** 2)))


# =========================
# LOCAL SILERO VAD
# =========================
class SileroVAD:
    def __init__(self):
        self.available = False
        self.model = None
        self.get_speech_timestamps = None

        try:
            log("LOAD", "Đang tải Silero VAD local...")
            log("PATH", SILERO_DIR)

            if not os.path.exists(SILERO_DIR):
                raise FileNotFoundError(f"Không tìm thấy Silero local: {SILERO_DIR}")

            self.model, utils = torch.hub.load(
                repo_or_dir=SILERO_DIR,
                model="silero_vad",
                source="local",
            )

            self.get_speech_timestamps = utils[0]
            self.available = True

            log("LOAD", "Silero VAD local OK")

        except Exception as e:
            self.available = False
            log("LOAD", "Không tải được Silero VAD, dùng RMS fallback")
            log("ERROR", str(e))

    def is_speech(self, audio: np.ndarray) -> bool:
        if audio.size == 0:
            return False

        rms = rms_value(audio)

        if rms < RMS_FALLBACK_THRESHOLD:
            return False

        if not self.available:
            return rms >= RMS_FALLBACK_THRESHOLD

        try:
            tensor = torch.from_numpy(audio.astype(np.float32))

            timestamps = self.get_speech_timestamps(
                tensor,
                self.model,
                sampling_rate=SAMPLE_RATE,
                threshold=VAD_THRESHOLD,
                min_speech_duration_ms=200,
                min_silence_duration_ms=150,
            )

            return len(timestamps) > 0

        except Exception as e:
            log("VAD_ERROR", str(e))
            return rms >= RMS_FALLBACK_THRESHOLD


vad = SileroVAD()


# =========================
# AUDIO BUFFER
# =========================
class AudioRingBuffer:
    def __init__(self, max_samples: int):
        self.max_samples = max_samples
        self.buffer = []
        self.total_samples = 0
        self.lock = threading.Lock()

    def append(self, audio: np.ndarray):
        if audio.size == 0:
            return

        audio = audio.astype(np.float32, copy=False)

        with self.lock:
            self.buffer.append(audio)
            self.total_samples += audio.size

            while self.total_samples > self.max_samples and self.buffer:
                removed = self.buffer.pop(0)
                self.total_samples -= removed.size

    def get_audio(self) -> np.ndarray:
        with self.lock:
            if not self.buffer:
                return np.array([], dtype=np.float32)
            return np.concatenate(self.buffer).astype(np.float32, copy=False)

    def clear(self):
        with self.lock:
            self.buffer.clear()
            self.total_samples = 0

    def size(self) -> int:
        with self.lock:
            return self.total_samples


# =========================
# SHERPA ONNX ENGINE
# =========================
class SherpaONNXEngine:
    def __init__(self):
        cpu_threads = max(1, min(4, os.cpu_count() or 4))
        log("LOAD", "Đang tải Sherpa-ONNX Zipformer local...")
        log("ENCODER", ENCODER_PATH)

        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=ENCODER_PATH,
            decoder=DECODER_PATH,
            joiner=JOINER_PATH,
            tokens=TOKENS_PATH,
            num_threads=cpu_threads,
            sample_rate=SAMPLE_RATE,
            feature_dim=80,
            decoding_method="greedy_search",
        )

        log("LOAD", "Sherpa-ONNX Zipformer OK")

    def transcribe(self, audio: np.ndarray, code_mode: bool = False) -> str:
        if audio.size < MIN_DECODE_SAMPLES:
            return ""

        try:
            t0 = time.perf_counter()

            stream = self.recognizer.create_stream()
            stream.accept_waveform(SAMPLE_RATE, audio)
            self.recognizer.decode_stream(stream)
            text = stream.result.text

            elapsed = time.perf_counter() - t0
            log("TIME", f"{elapsed:.2f}s")
            log("SHERPA_RAW", text)

            text = clean_text(text)

            if code_mode:
                text = apply_code_mode(text)

            log("CLEAN_TEXT", text)

            if is_bad_text(text):
                log("DROP", text)
                return ""

            return text

        except Exception as e:
            log("ERROR", f"transcribe: {e}")
            return ""


engine = SherpaONNXEngine()


# =========================
# SPEECH SESSION
# =========================
class SpeechSession:
    def __init__(self, websocket: WebSocket, loop: asyncio.AbstractEventLoop):
        self.websocket = websocket
        self.loop = loop

        self.audio_buffer = AudioRingBuffer(RING_BUFFER_SAMPLES)

        self.running = True
        self.code_mode = False
        self.last_decode_time = 0.0

        self.current_text = ""
        self.last_sent_text = ""

        self.last_voice_time = time.time()
        self.has_current_voice = False
        self.pcm_count = 0

        self.worker_thread = threading.Thread(
            target=self.worker_loop,
            daemon=True,
        )

    def start(self):
        self.worker_thread.start()

    def stop(self):
        self.running = False

    def add_audio(self, audio: np.ndarray):
        if audio.size == 0:
            return

        rms = rms_value(audio)
        is_voice = vad.is_speech(audio)

        self.pcm_count += 1
        if self.pcm_count % LOG_PCM_EVERY == 0 or is_voice:
            log("PCM", f"{audio.size} samples RMS={rms:.4f}")
            log("VAD", f"speech={is_voice}")

        if is_voice or self.has_current_voice:
            self.audio_buffer.append(audio)

            if is_voice:
                self.last_voice_time = time.time()
                self.has_current_voice = True

            return True

        return False

    async def safe_send(self, data: dict):
        try:
            await self.websocket.send_json(data)
        except Exception:
            self.running = False

    def send_from_thread(self, data: dict):
        if not self.running:
            return

        future = asyncio.run_coroutine_threadsafe(
            self.safe_send(data),
            self.loop,
        )

        try:
            future.result(timeout=2)
        except Exception:
            self.running = False

    def worker_loop(self):
        self.send_from_thread({
            "type": "status",
            "text": "Đã sẵn sàng nhận giọng nói"
        })

        while self.running:
            now = time.time()

            if self.has_current_voice:
                silence_time = now - self.last_voice_time

                if silence_time >= SILENCE_SECONDS_TO_COMMIT:
                    if self.current_text:
                        log("COMMIT", self.current_text)
                        self.send_from_thread({
                            "type": "append",
                            "text": self.current_text,
                        })

                    self.has_current_voice = False
                    self.current_text = ""
                    self.last_sent_text = ""
                    self.audio_buffer.clear()

                    self.send_from_thread({
                        "type": "status",
                        "text": "Đã tạm dừng, chờ câu tiếp theo"
                    })
                    time.sleep(0.05)
                    continue

            if now - self.last_decode_time < STEP_SECONDS:
                time.sleep(0.02)
                continue

            self.last_decode_time = now

            size = self.audio_buffer.size()

            if size < MIN_DECODE_SAMPLES:
                continue

            audio = self.audio_buffer.get_audio()
            if audio.size > MAX_WINDOW_SAMPLES:
                audio = audio[-MAX_WINDOW_SAMPLES:]

            if audio.size < MIN_DECODE_SAMPLES:
                continue

            log("DECODE", f"{len(audio) / SAMPLE_RATE:.2f}s")
            text = engine.transcribe(audio, code_mode=self.code_mode)

            log("SHERPA", text)

            if not text:
                continue

            self.current_text = text
            if text != self.last_sent_text:
                self.last_sent_text = text
                log("SEND", f"replace -> {text}")
                self.send_from_thread({
                    "type": "replace",
                    "text": text,
                })

            self.send_from_thread({
                "type": "status",
                "text": "Đang nghe..."
            })


async def handle_speech_websocket(websocket: WebSocket):
    import json
    await websocket.accept()

    log("WS", "client connected")

    loop = asyncio.get_running_loop()
    session = SpeechSession(websocket, loop)
    session.start()

    try:
        await websocket.send_json({
            "type": "status",
            "text": "Đã kết nối mô hình local + VAD local"
        })

        while session.running:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                data = message["bytes"]
                audio = pcm_bytes_to_float32(data)

                if audio.size > 0:
                    was_voice = session.add_audio(audio)

                    if was_voice:
                        await websocket.send_json({
                            "type": "voice"
                        })

            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    if payload.get("type") == "config":
                        session.code_mode = bool(payload.get("codeMode", False))
                        log("CONFIG", f"code_mode={session.code_mode}")
                except Exception as config_err:
                    log("ERROR", f"Config parse error: {config_err}")

    except Exception as e:
        msg = str(e)

        if (
            "disconnect" in msg.lower()
            or "websocket" in msg.lower()
            or "no_status_rcvd" in msg.lower()
            or "1005" in msg
        ):
            log("WS", "client disconnected")
        else:
            log("ERROR", f"WebSocket: {e}")

    finally:
        session.stop()
        log("WS", "session stopped")
