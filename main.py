import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

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

SYSTEM_PROMPT = "You are a friendly robot assistant. Keep answers short, clear, and helpful."

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000),
)

history = []


def make_config(model, low_thinking=True):
    kwargs = {"system_instruction": SYSTEM_PROMPT}
    if low_thinking and model.startswith("gemini-3"):
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="low")
    return types.GenerateContentConfig(**kwargs)


def ask(model, contents):
    for low in (True, False):  # retry without thinking settings if rejected
        try:
            r = client.models.generate_content(
                model=model, contents=contents, config=make_config(model, low)
            )
            return r.text or ""
        except Exception as e:
            if low and ("400" in str(e) or "INVALID_ARGUMENT" in str(e)):
                continue
            raise


def main():
    print("\nGemini Robot Assistant")
    print("Commands: 'exit' to quit, 'reset' to clear memory\n")
    print("Models:", ", ".join(MODELS), "\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            break
        if user_input.lower() == "reset":
            history.clear()
            print("Memory cleared.\n")
            continue

        contents = history + [
            types.Content(role="user", parts=[types.Part(text=user_input)])
        ]

        reply = None
        for model in MODELS:
            start = time.time()
            try:
                print(f"Robot ({model}): ", end="", flush=True)
                reply = ask(model, contents)
                print(f"{reply}  [{time.time() - start:.1f}s]\n")
                break
            except KeyboardInterrupt:
                print("\n[cancelled]\n")
                break
            except Exception as e:
                print(f"failed after {time.time() - start:.1f}s -> {str(e)[:150]}\n")

        if reply:
            history.append(contents[-1])
            history.append(types.Content(role="model", parts=[types.Part(text=reply)]))
        else:
            print("Robot: All models failed.\n")


if __name__ == "__main__":
    main()