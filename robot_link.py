import sys
import urllib.request

ROBOT_IP = "192.168.137.55"   # <- replace with the IP from the Serial Monitor


def send(direction: str, ms: int = 1000) -> str:
    url = f"http://{ROBOT_IP}/cmd?dir={direction}&ms={ms}"
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return r.read().decode()
    except Exception as e:
        return f"error: {e}"


if __name__ == "__main__":
    direction = sys.argv[1] if len(sys.argv) > 1 else "stop"
    print(send(direction))