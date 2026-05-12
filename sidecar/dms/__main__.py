from __future__ import annotations

import argparse
import json
import os
import secrets
import sys

import uvicorn

from dms.config import Paths
from dms.logging_setup import configure as configure_logging
from dms.server import create_app


def _emit_handshake(port: int, token: str) -> None:
    """In dev-browser mode the launcher reads a single line of JSON from stdout
    so the UI knows how to reach the sidecar. In container/web mode this is a
    no-op (handshake disabled via --no-handshake or DMS_WEB_MODE)."""
    payload = {"port": port, "token": token, "ready": True}
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(prog="dms-engine", description="AI DMS backend service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "0")),
                        help="0 = pick a free port (dev)")
    parser.add_argument(
        "--token",
        default=os.environ.get("DMS_BEARER_TOKEN") or "",
        help="Bearer token required on all requests. If empty, a random one is generated.",
    )
    parser.add_argument(
        "--no-handshake",
        action="store_true",
        default=bool(os.environ.get("DMS_WEB_MODE")),
        help="Skip the stdout handshake (container/web mode).",
    )
    args = parser.parse_args()

    if not args.token:
        # In web/container mode a random per-restart token would silently
        # break the UI (every redeploy would invalidate the bearer baked
        # into the Vercel build). Fail fast instead.
        if args.no_handshake or os.environ.get("DMS_WEB_MODE"):
            sys.stderr.write(
                "FATAL: DMS_BEARER_TOKEN env var is required in web mode "
                "(set it in Render → Environment).\n"
            )
            sys.exit(1)
        args.token = secrets.token_urlsafe(32)

    # If port = 0, bind a free port up-front so we can announce it before uvicorn starts.
    if args.port == 0:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((args.host, 0))
            args.port = s.getsockname()[1]

    os.environ["DMS_BEARER_TOKEN"] = args.token

    paths = Paths.resolve()
    configure_logging(paths.app_data, debug=bool(os.environ.get("DMS_DEBUG")))

    app = create_app(token=args.token)

    if not args.no_handshake:
        _emit_handshake(args.port, args.token)

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
