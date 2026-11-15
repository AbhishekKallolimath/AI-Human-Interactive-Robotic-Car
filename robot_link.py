import os

import requests
from dotenv import load_dotenv

load_dotenv()

_raw = os.getenv("ROBOT_IP", "robotcar.local").strip()
_raw = _raw.replace("http://", "").replace("https://", "").strip("/")
BASE_URL = f"http://{_raw}"
MOVE_TIMEOUT = 3


def send(direction: str, ms: int | None = None) -> str:
    """Send forward/backward/left/right/stop to the ESP32.
    Returns the car's reply ('ok ...', 'blocked: ...') or 'error: ...'."""
    params = {"ms": int(ms)} if ms and direction != "stop" else None
    try:
        r = requests.get(f"{BASE_URL}/{direction}", params=params, timeout=MOVE_TIMEOUT)
        r.raise_for_status()
        return r.text.strip()
    except requests.RequestException as e:
        return f"error: {str(e)[:100]}"


def get_sensors(timeout: float = 2.0) -> dict:
    """Read /sensors from the ESP32. Returns a dict, or {'error': ...}."""
    try:
        r = requests.get(f"{BASE_URL}/sensors", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        return {"error": str(e)[:100]}


if __name__ == "__main__":
    print("Car link:", send("stop"))
    print("Sensors:", get_sensors())