"""NetTwin entrypoint: python run.py -> http://127.0.0.1:8000"""
import argparse

import uvicorn

from nettwin.api.app import create_app
from nettwin.config import load_settings
from nettwin.config_check import validate_startup
from nettwin.logging_config import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="NetTwin server")
    parser.add_argument("--host", help="bind host")
    parser.add_argument("--port", type=int, help="bind port")
    args = parser.parse_args()

    setup_logging()
    settings = load_settings()
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    validate_startup(settings)
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
