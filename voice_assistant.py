import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from stt import calibrate, listen, transcribe   # speech-to-text
from robot_link import send                      # ESP32 link
from tts import speak                            # ElevenLabs voice (Windows voice as fallback)

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not found in .env file")
    raise SystemExit(1)

MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]

TIMEOUT_SECONDS = 20
MAX_HISTORY = 20

DEFAULT_MOVE_MS = 1000
MAX_MOVE_MS = 3000

SYSTEM_PROMPT = (
    "You are the voice of a small robot car. Talk like a warm, natural person: "
    "casual, curious and a little playful, never stiff or robotic. "
    "You can chat about anything and answer any question, from school and science "
    "to jokes, advice and general knowledge. "
    "Your replies are spoken aloud, so use plain spoken English with no markdown, "
    "lists, emojis or symbols. "
    "Keep answers short by default, one to three sentences, but go longer when the "
    "person asks for an explanation or a story. "
    "You do not move the car yourself. The car only moves when the person says "
    "exactly: move front, move back, move left, move right, or stop. "
    "If someone asks you to drive in some other way, kindly remind them of those commands."
)

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000),
)

history: list[types.Content] = []

# ---------------------------------------------------------------- commands
# The car moves ONLY for: move front / back / left / right (optionally
# "for two seconds") and stop. Everything else is normal conversation.

MOVE_VERBS = ("move",)    # add "go" or "turn" here if you want more verbs later
STOP_WORDS = {"stop", "halt", "freeze"}
FILLER = {"ok", "okay", "hey", "robot", "please", "can", "could", "would", "you", "now"}
DIRECTIONS = {
    "front": "forward", "forward": "forward", "forwards": "forward", "ahead": "forward",
    "back": "backward", "backward": "backward", "backwards": "backward",
    "left": "left",
    "right": "right",
}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3}


def parse_command(text: str):
    """Return ('stop', 0), (direction, ms), or None if it's just conversation."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words:
        return None

    # stopping is always safe, so a short sentence containing "stop" stops the car
    if len(words) <= 5 and any(w in STOP_WORDS for w in words):
        return ("stop", 0)

    while words and words[0] in FILLER:          # "ok can you move left please"
        words.pop(0)
    while words and words[-1] in ("please", "now"):
        words.pop()

    if len(words) < 2 or words[0] not in MOVE_VERBS:
        return None

    rest = words[1:]
    if rest and rest[0] == "to":                 # "move to the left"
        rest = rest[1:]
    if rest and rest[0] == "the":
        rest = rest[1:]
    if not rest or rest[0] not in DIRECTIONS:
        return None

    direction = DIRECTIONS[rest[0]]
    tail = rest[1:]
    ms = DEFAULT_MOVE_MS
    if tail:                                     # optional: "for two seconds"
        t = tail[1:] if tail[0] == "for" else tail
        if len(t) == 2 and t[1] in ("second", "seconds"):
            n = int(t[0]) if t[0].isdigit() else NUMBER_WORDS.get(t[0])
            if not n:
                return None
            ms = n * 1000
        else:
            return None
    return (direction, min(ms, MAX_MOVE_MS))


def run_command(direction: str, ms: int) -> str:
    result = send("stop") if direction == "stop" else send(direction, ms)
    if result.startswith("error"):
        print(f"  [robot link] {result}")
        return "I can't reach the car right now."
    return "Okay, stopping." if direction == "stop" else f"Okay, moving {direction}."

# ------------------------------------------------------------------ gemini


def make_config(model: str, low_thinking: bool = True):
    kwargs = {"system_instruction": SYSTEM_PROMPT}
    if low_thinking and model.startswith("gemini-3"):
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="low")
    return types.GenerateContentConfig(**kwargs)


def call_model(model: str, contents) -> str:
    for low in (True, False):
        try:
            r = client.models.generate_content(
                model=model, contents=contents, config=make_config(model, low)
            )
            return r.text or ""
        except Exception as e:
            if low and ("400" in str(e) or "INVALID_ARGUMENT" in str(e)):
                continue
            raise


def ask_gemini(user_text: str) -> str | None:
    contents = history + [
        types.Content(role="user", parts=[types.Part(text=user_text)])
    ]
    for model in MODELS:
        start = time.time()
        try:
            reply = call_model(model, contents)
            if reply.strip():
                print(f"  ({model}, {time.time() - start:.1f}s)")
                history.append(contents[-1])
                history.append(
                    types.Content(role="model", parts=[types.Part(text=reply)])
                )
                del history[:-MAX_HISTORY]
                return reply.strip()
        except Exception as e:
            print(f"  [{model} failed after {time.time() - start:.1f}s: {str(e)[:100]}]")
    return None

# -------------------------------------------------------------------- main


def main():
    print("\nRobot Voice Assistant")
    print("Say 'move front', 'move back', 'move left', 'move right' or 'stop'.")
    print("Anything else is a normal conversation.")
    print("Say 'goodbye' to quit, or 'reset' to clear memory.\n")

    link = send("stop")
    print(f"Car link: {link}\n")

    threshold = calibrate()
    speak("Hello, I am ready." if not link.startswith("error")
          else "Hello. I am ready, but I can't reach the car.")

    while True:
        print("Listening...", flush=True)
        audio = listen(threshold)
        if audio is None:
            continue

        text = transcribe(audio)
        if not text:
            continue
        print(f"You: {text}")

        command = text.lower().strip()
        if command in ("goodbye", "exit", "quit", "bye"):
            send("stop")
            speak("Goodbye!")
            break
        if command == "reset":
            history.clear()
            speak("Memory cleared.")
            continue

        # 1) the five driving commands are handled locally, instantly
        parsed = parse_command(text)
        if parsed:
            direction, ms = parsed
            reply = run_command(direction, ms)
            print(f"Robot: {reply}\n")
            speak(reply)
            continue

        # 2) everything else is a normal conversation with Gemini
        print("Thinking...", flush=True)
        reply = ask_gemini(text) or "Sorry, I couldn't reach my brain. Try again in a moment."
        print(f"Robot: {reply}\n")
        speak(reply)
        time.sleep(0.3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye!")
    finally:
        send("stop")   # always stop the car when the program ends