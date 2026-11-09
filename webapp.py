import os
import urllib.request

from flask import Flask, jsonify, request, send_from_directory

from robot_link import send, ROBOT_IP                              # ESP32 link
from voice_assistant import ask_gemini, parse_command, run_command  # Gemini + keyword driving

# "127.0.0.1" = only this laptop. Use "0.0.0.0" to open it to your phone on the
# same Wi-Fi (anyone on that Wi-Fi could then drive the car).
HOST = "127.0.0.1"
PORT = 5000
HOLD_MAX_MS = 600          # longest single pulse from the hold-to-drive buttons

BASE = os.path.dirname(os.path.abspath(__file__))
DIRECTIONS = {"forward", "backward", "left", "right"}

app = Flask(__name__)


@app.get("/")
def index():
    return send_from_directory(BASE, "index.html")


@app.get("/api/status")
def status():
    try:
        urllib.request.urlopen(f"http://{ROBOT_IP}/", timeout=1.5).read()
        return jsonify(online=True, ip=ROBOT_IP)
    except Exception:
        return jsonify(online=False, ip=ROBOT_IP)


@app.post("/api/drive")
def drive():
    data = request.get_json(silent=True) or {}
    direction = data.get("dir")
    if direction == "stop":
        return jsonify(result=send("stop"))
    if direction not in DIRECTIONS:
        return jsonify(error="unknown direction"), 400
    try:
        ms = int(data.get("ms") or 400)
    except (TypeError, ValueError):
        ms = 400
    return jsonify(result=send(direction, max(100, min(ms, HOLD_MAX_MS))))


@app.post("/api/chat")
def chat():
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if not text:
        return jsonify(error="Type or say something first."), 400

    parsed = parse_command(text)          # driving words are handled locally
    if parsed:
        direction, ms = parsed
        return jsonify(reply=run_command(direction, ms), action=direction)

    reply = ask_gemini(text) or "I couldn’t reach Gemini. Try again in a moment."
    return jsonify(reply=reply, action=None)


if __name__ == "__main__":
    print(f"\nRobot console: http://{'localhost' if HOST == '127.0.0.1' else HOST}:{PORT}")
    print(f"Car at http://{ROBOT_IP}\n")
    try:
        app.run(host=HOST, port=PORT, threaded=True)
    finally:
        send("stop")