from __future__ import annotations

import argparse
import uvicorn

from .config import settings


def main():
    parser = argparse.ArgumentParser(description="Run Dürer's Hoard on loopback")
    parser.add_argument("--host", default=settings().host)
    parser.add_argument("--port", type=int, default=settings().port)
    args = parser.parse_args()
    uvicorn.run("durer_hoard.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
