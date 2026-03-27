"""Entry point for the Python sidecar server."""

import uvicorn


def main():
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
