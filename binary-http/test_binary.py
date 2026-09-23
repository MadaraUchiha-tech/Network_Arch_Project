#!/usr/bin/env python3
"""Tests for BCP1 bserve/bcurl."""

import os
import socket
import subprocess
import sys
import time

from protocol import (
    FRAME_REQUEST,
    FRAME_RESPONSE,
    METHOD_GET,
    ProtocolError,
    decode_request,
    decode_response,
    encode_frame,
    encode_request,
    encode_response,
    read_frame,
)

ROOT = os.path.join(os.path.dirname(__file__), "www")


def pick_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port):
    proc = subprocess.Popen(
        [sys.executable, "bserve", ROOT, str(port)],
        cwd=os.path.dirname(__file__),
    )
    time.sleep(0.3)
    return proc


def test_fetch_index(port):
    result = subprocess.run(
        [sys.executable, "bcurl", f"localhost:{port}/index.html"],
        cwd=os.path.dirname(__file__),
        capture_output=True,
    )
    assert result.returncode == 0
    assert b"Hello from BCP1" in result.stdout
    print("PASS: bcurl fetches index.html")


def test_404(port):
    result = subprocess.run(
        [sys.executable, "bcurl", f"localhost:{port}/missing.html"],
        cwd=os.path.dirname(__file__),
        capture_output=True,
    )
    assert result.returncode != 0
    print("PASS: bcurl exits non-zero on 404")


def test_persistent_connection(port):
    """Two requests on one socket — connection stays open."""
    sock = socket.create_connection(("localhost", port))

    sock.sendall(encode_request(METHOD_GET, "/about.txt", indexed=[(2, "localhost")]))
    ft, payload = read_frame(sock)
    assert ft == FRAME_RESPONSE
    resp = decode_response(payload)
    assert resp["status"] == 200
    assert b"BCP1 file server" in resp["body"]

    sock.sendall(encode_request(METHOD_GET, "/index.html", indexed=[(2, "localhost")]))
    ft, payload = read_frame(sock)
    resp = decode_response(payload)
    assert resp["status"] == 200

    assert sock.fileno() != -1
    sock.close()
    print("PASS: two requests on one TCP connection")


def test_unknown_frame_skipped(port):
    """Server must skip unknown frame types and still read the REQUEST."""
    sock = socket.create_connection(("localhost", port))

    # Unknown type 0x99 with 4-byte payload
    junk = encode_frame(0x99, b"SKIP")
    req = encode_request(METHOD_GET, "/about.txt", indexed=[(2, "localhost")])
    sock.sendall(junk + req)

    ft, payload = read_frame(sock)
    assert ft == FRAME_RESPONSE
    resp = decode_response(payload)
    assert resp["status"] == 200
    sock.close()
    print("PASS: unknown frame type skipped (forward compatibility)")


def test_malformed_request(port):
    """Truncated request payload -> 400."""
    sock = socket.create_connection(("localhost", port))
    bad = encode_frame(FRAME_REQUEST, b"\x01\x00")  # too short
    sock.sendall(bad)
    ft, payload = read_frame(sock)
    assert ft == FRAME_RESPONSE
    resp = decode_response(payload)
    assert resp["status"] == 400
    sock.close()
    print("PASS: malformed request -> 400")


def test_verbose_mode(port):
    result = subprocess.run(
        [sys.executable, "bcurl", "-v", f"localhost:{port}/about.txt"],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "REQUEST frame" in result.stdout
    assert "RESPONSE frame" in result.stdout
    print("PASS: -v prints hexdump")


def generate_hexdump_sample():
    """Helper to print bytes for annotated_hexdump.md (run manually)."""
    req = encode_request(METHOD_GET, "/about.txt", indexed=[(2, "localhost")])
    body = b"BCP1 file server demo.\n"
    resp = encode_response(200, body, indexed=[(3, "text/plain")])
    print("REQUEST:", req.hex())
    print("RESPONSE:", resp.hex())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--hex":
        generate_hexdump_sample()
        sys.exit(0)

    port = pick_free_port()
    proc = start_server(port)
    try:
        test_fetch_index(port)
        test_404(port)
        test_persistent_connection(port)
        test_unknown_frame_skipped(port)
        test_malformed_request(port)
        test_verbose_mode(port)
        print("\nAll binary-http tests passed.")
    finally:
        proc.terminate()
        proc.wait()
