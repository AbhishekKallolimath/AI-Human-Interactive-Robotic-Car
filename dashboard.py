"""Rover dashboard backend. Run: python dashboard.py  ->  http://localhost:5001
Put this file next to voice_assistant.py and robot_link.py, and index.html in a folder named static."""
import os

from flask import Flask, jsonify, request, send_from_directory

import stt
import voice_assistant as va
from robot_link import send, get_sensors

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static")
MOVES = ("forward", "backward", "left", "right", "stop")
_threshold = None


@app.get("/")
def index():
    for folder in (os.path.join(BASE, "static"), BASE):
        if os.path.isfile(os.path.join(folder, "index.html")):
            return send_from_directory(folder, "index.html")
    return f"index.html not found. Put it here: {os.path.join(BASE, 'static', 'index.html')}", 404


@app.get("/api/sensors")
def sensors():
    return jsonify(get_sensors(1.5))


@app.post("/api/move")
def move():
    data = request.get_json(silent=True) or {}
    d = data.get("dir")
    if d not in MOVES:
        return jsonify(reply="error: unknown command"), 400
    ms = max(100, min(int(data.get("ms", 1000)), va.MAX_MOVE_MS))
    return jsonify(reply=send("stop") if d == "stop" else send(d, ms))


@app.post("/api/listen")
def listen_mic():
    global _threshold
    if _threshold is None:                 # calibrates once, on the first click
        _threshold = stt.calibrate()
    audio = stt.listen(_threshold)
    if audio is None:
        return jsonify(text="")
    return jsonify(text=stt.transcribe(audio) or "")


@app.post("/api/chat")
def chat():
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if not text:
        return jsonify(reply="", kind="none")
    cmd = va.parse_command(text)
    if cmd:                                   # same rules as the voice assistant
        return jsonify(reply=va.run_command(*cmd), kind="drive")
    kind = va.parse_sensor_query(text)
    if kind:
        return jsonify(reply=va.run_sensor_query(kind), kind="sensor")
    reply = va.ask_gemini(text) or "Sorry, I couldn't reach my brain. Try again in a moment."
    return jsonify(reply=reply, kind="chat")


if __name__ == "__main__":
    print("Rover dashboard: http://localhost:5001")
    try:
        app.run(host="127.0.0.1", port=5001, debug=False)
    finally:
        send("stop")