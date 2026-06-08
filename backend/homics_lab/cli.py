import argparse
import sys
import uvicorn

from homics_lab.config import settings


def main():
    parser = argparse.ArgumentParser(description="HomicsLab - Bioinformatics Agent")
    parser.add_argument(
        "command",
        choices=["start", "version"],
        help="Command to run",
    )
    parser.add_argument("--host", default=settings.host, help="Host to bind")
    parser.add_argument("--port", type=int, default=settings.port, help="Port to bind")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    if args.command == "version":
        from homics_lab import __version__

        print(f"HomicsLab {__version__}")
        return

    if args.command == "start":
        print(f"Starting HomicsLab on http://{args.host}:{args.port}")
        uvicorn.run(
            "homics_lab.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )


if __name__ == "__main__":
    main()
