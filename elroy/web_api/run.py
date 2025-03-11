#!/usr/bin/env python
import argparse
import os

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run the Elroy Web API server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (default: 1)")

    args = parser.parse_args()

    # Set environment variables for configuration
    if args.debug:
        os.environ["ELROY_API_DEBUG"] = "1"

    # Run the server
    uvicorn.run(
        "elroy.web_api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()
