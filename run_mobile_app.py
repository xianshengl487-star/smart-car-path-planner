from __future__ import annotations

import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "mobile_app"
PORT = 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)


def main() -> None:
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as server:
        print(f"Mobile planner serving at http://0.0.0.0:{PORT}/")
        print("On your phone, open http://<this-computer-ip>:8765/")
        server.serve_forever()


if __name__ == "__main__":
    main()
