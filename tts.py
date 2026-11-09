import os
import re

import numpy as np
import pyttsx3
import sounddevice as sd
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
MODEL_ID = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")   # fast, low latency
PCM_RATE = 24000                                                  # matches "pcm_24000"
FALLBACK_RATE = 175                                               # Windows voice speed

_client = None
_warned = False


def _eleven():
    global _client
    if _client is None:
        from elevenlabs.client import ElevenLabs
        _client = ElevenLabs(api_key=API_KEY)
    return _client


def clean_for_speech(text: str) -> str:
    text = re.sub(r"[*_#`>~|]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _speak_elevenlabs(text: str):
    audio = _eleven().text_to_speech.convert(
        text=text,
        voice_id=VOICE_ID,
        model_id=MODEL_ID,
        output_format=f"pcm_{PCM_RATE}",
    )
    buf = b""
    with sd.RawOutputStream(samplerate=PCM_RATE, channels=1, dtype="int16") as out:
        for chunk in audio:                      # play while it is still arriving
            buf += chunk
            n = len(buf) - (len(buf) % 2)        # keep whole 16-bit samples
            if n:
                out.write(buf[:n])
                buf = buf[n:]


def _speak_windows(text: str):
    engine = pyttsx3.init()
    engine.setProperty("rate", FALLBACK_RATE)
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def speak(text: str):
    """Speak in the cloned ElevenLabs voice; fall back to the Windows voice on any problem."""
    global _warned
    text = clean_for_speech(text)
    if not text:
        return

    if API_KEY and VOICE_ID:
        try:
            _speak_elevenlabs(text)
            return
        except Exception as e:
            print(f"  [ElevenLabs failed, using Windows voice: {str(e)[:160]}]")
    elif not _warned:
        print("  [ElevenLabs not set up (missing key or voice ID in .env), using Windows voice]")
        _warned = True

    _speak_windows(text)


if __name__ == "__main__":
    speak("Hello! This is my new voice. How do I sound?")