"""Disposable Compose proof of proxy identity; refuses non-CI execution."""

import hashlib
import json
import os
import socket
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from redis import Redis

from platform_core.config import get_settings


def main() -> None:
    if os.environ.get("CI_PROXY_TEST") != "1":
        raise RuntimeError("proxy smoke requires an explicitly disposable CI deployment")
    username = "ci-proxy-identity"
    with socket.create_connection(("caddy", 80), timeout=5) as connection:
        source_ip = connection.getsockname()[0]
    key = "admin:login:" + hashlib.sha256((source_ip + ":" + username).encode()).hexdigest()
    redis = Redis.from_url(get_settings().redis_url)
    before = int(redis.get(key) or 0)
    headers = {
        "Host": "localhost", "Origin": "https://localhost", "Content-Type": "application/json",
        "X-Forwarded-For": "203.0.113.123", "X-Real-IP": "203.0.113.123",
    }
    payload = json.dumps({"username": username, "password": "intentionally wrong CI password"}).encode()
    for url in ("http://caddy/api/admin/login", "http://api:8000/api/admin/login"):
        request = Request(url, data=payload, headers=headers)
        try:
            with urlopen(request, timeout=10):
                raise AssertionError("unknown CI user unexpectedly authenticated")
        except HTTPError as exc:
            assert exc.code == 401, f"unexpected login response: {exc.code}"
    assert int(redis.get(key) or 0) == before + 2, "client identity collapsed or spoofed"
    spoofed = "admin:login:" + hashlib.sha256(("203.0.113.123:" + username).encode()).hexdigest()
    assert redis.get(spoofed) is None, "untrusted forwarded identity accepted"
    redis.close()
    print("Proxy identity smoke passed: trusted forwarding and direct-header rejection")


if __name__ == "__main__":
    main()
