"""Start the app:  python run.py   ->  http://127.0.0.1:8000

If the port is unavailable (already in use, or reserved by Windows: WinError 10013 / 10048)
the next free port is used and printed. Set PLANNER_PORT in .env to choose the first port to try.
"""
import socket
import sys

import uvicorn

from config.settings import HOST, PORT


def free_port(host: str, start: int, tries: int = 25) -> int:
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:          # in use, or forbidden by Windows' reserved port ranges
                continue
    raise SystemExit(f"No free port between {start} and {start + tries - 1}. Set PLANNER_PORT to another value.")


def main() -> None:
    port = free_port(HOST, PORT)
    if port != PORT:
        print(f"Port {PORT} is not available on this machine, using {port} instead.", file=sys.stderr)
    print(f"\n  Evacuation Planner:  http://{HOST}:{port}\n", flush=True)
    uvicorn.run("backend.main:app", host=HOST, port=port, reload=False)


if __name__ == "__main__":
    main()