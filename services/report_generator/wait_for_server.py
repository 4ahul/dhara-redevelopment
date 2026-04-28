import sys
import time

import httpx


def wait(url="http://127.0.0.1:8085/health", timeout_s=30):
    start = time.time()
    last_err = None
    while time.time() - start < timeout_s:
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                print("server is up")
                return 0
        except Exception as e:
            last_err = e
        time.sleep(0.5)
    print(f"server not responding within {timeout_s}s: {last_err}")
    return 1


if __name__ == "__main__":
    sys.exit(wait())
