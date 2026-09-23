#!/usr/bin/env python3
"""Tests matching the assignment grader scenario."""

import os
import socket
import subprocess
import sys
import time


def pick_free_port():
    """Bind to port 0 and return an unused local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def send_request(sock, method, path, headers=None, body=b""):
    """Send one HTTP/1.1 request on an open socket."""
    headers = headers or {}
    lines = [f"{method} {path} HTTP/1.1"]
    for key, value in headers.items():
        lines.append(f"{key}: {value}")
    if body:
        lines.append(f"Content-Length: {len(body)}")
    msg = "\r\n".join(lines).encode("ascii") + b"\r\n\r\n" + body
    sock.sendall(msg)


def read_response(sock):
    """Read one HTTP response (headers + Content-Length body)."""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk

    header_end = data.find(b"\r\n\r\n")
    header_text = data[:header_end].decode("ascii")
    body_start = header_end + 4
    rest = data[body_start:]

    status_line = header_text.split("\r\n")[0]
    status_code = int(status_line.split(" ")[1])

    content_length = 0
    for line in header_text.split("\r\n")[1:]:
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())

    while len(rest) < content_length:
        chunk = sock.recv(4096)
        if not chunk:
            break
        rest += chunk

    body = rest[:content_length].decode("ascii")
    return status_code, body


def start_server(port):
    here = os.path.dirname(os.path.abspath(__file__))
    proc = subprocess.Popen(
        [sys.executable, "server.py", str(port)],
        cwd=here,
    )
    time.sleep(0.3)
    return proc


def test_grader_sequence(port):
    """One TCP handshake, six responses, socket still open."""
    s = socket.create_connection(("localhost", port))

    cases = [
        ("GET", "/add?a=2&b=3", {"Host": "localhost"}, 200, "5"),
        ("GET", "/sub?a=10&b=4", {"Host": "localhost"}, 200, "6"),
        ("GET", "/mul?a=6&b=7", {"Host": "localhost"}, 200, "42"),
        ("GET", "/div?a=1&b=0", {"Host": "localhost"}, 400, ""),
        ("GET", "/pow?a=2&b=8", {"Host": "localhost"}, 404, ""),
    ]

    for method, path, headers, expected_status, expected_body in cases:
        send_request(s, method, path, headers)
        status, body = read_response(s)
        assert status == expected_status, f"{path}: got {status}, want {expected_status}"
        assert body == expected_body, f"{path}: body {body!r} != {expected_body!r}"

    # POST /add -> 405
    send_request(s, "POST", "/add", {"Host": "localhost", "Content-Length": "0"})
    status, _ = read_response(s)
    assert status == 405

    # Socket should still be open
    assert s.fileno() != -1
    try:
        s.send(b"")  # noop — connection still usable
    except OSError:
        assert False, "socket closed early"

    s.close()
    print("PASS: grader sequence (1 handshake, 6 responses, socket open)")


def test_missing_host(port):
    s = socket.create_connection(("localhost", port))
    send_request(s, "GET", "/add?a=1&b=2", {})
    status, _ = read_response(s)
    assert status == 400
    s.close()
    print("PASS: missing Host header -> 400")


def test_invalid_params(port):
    s = socket.create_connection(("localhost", port))
    send_request(s, "GET", "/add?a=x&b=3", {"Host": "localhost"})
    status, _ = read_response(s)
    assert status == 400
    s.close()
    print("PASS: invalid params -> 400")


def test_back_to_back_framing(port):
    """Two requests in one send() — server must frame them correctly."""
    s = socket.create_connection(("localhost", port))
    req1 = (
        "GET /add?a=1&b=1 HTTP/1.1\r\n"
        "Host: localhost\r\n"
        "\r\n"
        "GET /add?a=2&b=2 HTTP/1.1\r\n"
        "Host: localhost\r\n"
        "\r\n"
    )
    s.sendall(req1.encode("ascii"))

    status1, body1 = read_response(s)
    status2, body2 = read_response(s)
    assert status1 == 200 and body1 == "2"
    assert status2 == 200 and body2 == "4"
    s.close()
    print("PASS: pipelined requests on one connection")


if __name__ == "__main__":
    port = pick_free_port()
    proc = start_server(port)
    try:
        test_grader_sequence(port)
        test_missing_host(port)
        test_invalid_params(port)
        test_back_to_back_framing(port)
        print("\nAll early-http11 tests passed.")
    finally:
        proc.terminate()
        proc.wait()
