"""Start the local web app: ``python -m sp_designer`` or ``sp-designer``."""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from .api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Spark Plug Designer (local web app)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args()
    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    print(f"Spark Plug Designer running at {url}")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
