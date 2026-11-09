from collections import deque

import numpy as np
import sounddevice as sd
import speech_recognition as sr

SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.1
SILENCE_SECONDS = 1.5     # stop after this much quiet
MAX_SECONDS = 10
WAIT_FOR_SPEECH = 8
LANGUAGE = "en-IN"

START_MULT = 2.0          # speech starts at noise x 2 (was x 3)
MIN_THRESHOLD = 150       # never go below this
END_FACTOR = 0.6          # quiet trailing words still count as speech
TARGET_PEAK = 0.7         # amplify recording so its loudest point hits 70%
MAX_GAIN = 30             # never amplify more than 30x

recognizer = sr.Recognizer()
BLOCK = int(SAMPLE_RATE * BLOCK_SECONDS)


def rms(data) -> float:
    return float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))


def calibrate(seconds: float = 1.0) -> float:
    print("Calibrating background noise... stay quiet for a second.")
    data = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                  channels=1, dtype="int16")
    sd.wait()
    noise = rms(data)
    threshold = max(noise * START_MULT, MIN_THRESHOLD)
    print(f"Noise level: {noise:.0f}  ->  speech threshold: {threshold:.0f}\n")
    return threshold


def boost(audio):
    """Amplify quiet recordings. Returns (audio, gain_used)."""
    audio = audio.astype(np.float32)
    peak = float(np.max(np.abs(audio)))
    if peak < 1:
        return audio.astype(np.int16), 1.0
    gain = min(TARGET_PEAK * 32767 / peak, MAX_GAIN)
    boosted = np.clip(audio * gain, -32768, 32767).astype(np.int16)
    return boosted, gain


def listen(threshold: float):
    """Record one phrase. Returns AudioData, or None if no speech."""
    preroll = deque(maxlen=5)   # 0.5 s before speech, so quiet starts aren't cut
    frames = []
    started = False
    silent = 0
    waited = 0
    end_threshold = threshold * END_FACTOR

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=BLOCK) as stream:
        while True:
            data, _ = stream.read(BLOCK)
            level = rms(data)

            if not started:
                preroll.append(data)
                if level > threshold:
                    started = True
                    frames.extend(preroll)
                else:
                    waited += 1
                    if waited * BLOCK_SECONDS > WAIT_FOR_SPEECH:
                        return None
            else:
                frames.append(data)
                silent = 0 if level > end_threshold else silent + 1
                if (silent * BLOCK_SECONDS >= SILENCE_SECONDS
                        or len(frames) * BLOCK_SECONDS >= MAX_SECONDS):
                    break

    audio = np.concatenate(frames).flatten()
    peak_before = int(np.max(np.abs(audio)))
    audio, gain = boost(audio)
    print(f"  (peak level {peak_before}, gain applied x{gain:.1f})")
    return sr.AudioData(audio.tobytes(), SAMPLE_RATE, 2)


def transcribe(audio) -> str | None:
    try:
        return recognizer.recognize_google(audio, language=LANGUAGE)
    except sr.UnknownValueError:
        print("  (couldn't understand that)")
    except sr.RequestError as e:
        print(f"  (speech service error: {e})")
    return None


def main():
    print("\nVoice test: speak after you see 'Listening...'. Say 'exit' to quit.\n")
    threshold = calibrate()

    while True:
        print("Listening...", flush=True)
        audio = listen(threshold)
        if audio is None:
            print("  (no speech heard)\n")
            continue

        print("Recognizing...", flush=True)
        text = transcribe(audio)
        if text:
            print(f"You said: {text}\n")
            if text.lower().strip() in ("exit", "quit", "stop listening"):
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye!")