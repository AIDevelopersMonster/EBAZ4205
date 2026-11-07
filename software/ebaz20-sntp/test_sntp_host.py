#!/usr/bin/env python3
"""Local simulated SNTP server; never touches host system time."""
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path

BINARY = Path(__file__).resolve().parent / "sntp-host-test"
EPOCH = 2208988800

def stamp(unix):
    value = unix + EPOCH
    sec = int(value)
    return struct.pack("!II", sec & 0xFFFFFFFF, int((value - sec) * 2**32))

def trial(case):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    errors = []

    def serve():
        try:
            req, addr = server.recvfrom(512)
            assert len(req) == 48
            data = bytearray(48)
            data[0] = 0x24
            data[1] = 2
            data[24:32] = req[40:48]
            now = time.time()
            data[32:40] = stamp(now - 0.005)
            data[40:48] = stamp(now)
            if case == "invalid-stratum":
                data[1] = 0
            if case == "invalid-originate":
                data[24] ^= 1
            server.sendto(data, addr)
        except Exception as exc:
            errors.append(str(exc))
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    run = subprocess.run(
        [str(BINARY), "--server", "127.0.0.1", "--port", str(port)],
        capture_output=True, text=True, timeout=6
    )
    thread.join(timeout=1)
    assert not errors, errors
    if case == "valid":
        assert run.returncode == 0, (run.stdout, run.stderr)
        assert "EBAZ20_SNTP_QUERY_PASS" in run.stdout
        assert "EBAZ20_SNTP_DRY_RUN_PASS" in run.stdout
    else:
        assert run.returncode != 0, (run.stdout, run.stderr)
        assert "failed validation" in run.stderr, run.stderr
    print("HOST_TEST_PASS", case)

if __name__ == "__main__":
    for case in ("valid", "invalid-stratum", "invalid-originate"):
        trial(case)
