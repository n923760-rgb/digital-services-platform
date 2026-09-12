import os
import sys
import time
from urllib.request import urlopen


def main() -> int:
    target = sys.argv[1]
    if target.startswith("file://"):
        path = target.removeprefix("file://")
        return 0 if os.path.exists(path) and time.time() - os.stat(path).st_mtime < 60 else 1
    try:
        with urlopen(target, timeout=3) as response:
            return 0 if response.status == 200 else 1
    except (OSError, TimeoutError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
