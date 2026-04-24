import socket
import time
import sys
import argparse

def wait_for_port(host, port, timeout=60):
    """Wait until a port is open on a host."""
    start_time = time.time()
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                print(f"[OK] {host}:{port} is open.")
                return True
        except (OSError, ConnectionRefusedError):
            elapsed = time.time() - start_time
            if elapsed > timeout:
                print(f"[ERROR] Timeout waiting for {host}:{port} after {timeout} seconds.")
                return False
            print(f"Waiting for {host}:{port}...")
            time.sleep(2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("port", type=int)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    
    if not wait_for_port(args.host, args.port, args.timeout):
        sys.exit(1)
