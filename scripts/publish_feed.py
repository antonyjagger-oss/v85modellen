#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib import request, error


def parse_args():
    parser = argparse.ArgumentParser(description="Build and publish V85Modellen feed to Render.")
    parser.add_argument(
        "--build-script",
        default="/home/dodge/workspace/v85modellen/scripts/build_feed.py",
        help="Path to feed builder script",
    )
    parser.add_argument(
        "--feed-path",
        default="/home/dodge/workspace/v85modellen/public/data/feed.json",
        help="Path to generated feed JSON",
    )
    parser.add_argument(
        "--post-url",
        default="https://v85modellen.onrender.com/api/feed",
        help="Target feed API URL",
    )
    parser.add_argument(
        "--secret-file",
        default="/home/dodge/workspace/v85modellen/.feed_secret",
        help="File containing FEED_SECRET",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip build step and publish existing feed JSON",
    )
    return parser.parse_args()


def load_secret(secret_file: str) -> str:
    env_secret = os.environ.get("FEED_SECRET", "").strip()
    if env_secret:
        return env_secret
    path = Path(secret_file)
    if not path.exists():
        raise FileNotFoundError(f"Secret file not found: {path}")
    return path.read_text().strip()


def run_build(build_script: str):
    subprocess.run([sys.executable, build_script], check=True)


def publish(feed_path: str, post_url: str, secret: str):
    body = Path(feed_path).read_bytes()
    req = request.Request(
        post_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-feed-secret": secret,
        },
    )
    with request.urlopen(req, timeout=60) as resp:
        payload = resp.read().decode("utf-8", errors="replace")
        return resp.status, payload


def main():
    args = parse_args()
    if not args.skip_build:
        run_build(args.build_script)

    secret = load_secret(args.secret_file)
    status, payload = publish(args.feed_path, args.post_url, secret)
    print(f"POST {args.post_url} -> {status}")
    print(payload)


if __name__ == "__main__":
    try:
        main()
    except error.HTTPError as exc:
        print(f"HTTPError {exc.code}")
        print(exc.read().decode('utf-8', errors='replace'))
        raise
