#!/usr/bin/env python3
"""
Early HTTP/1.1 calculator server.

Listens on one TCP socket and serves many requests on the same connection.
The hard part is framing: consume exactly one request before reading the next.
"""

import socket
import sys
from urllib.parse import parse_qs, urlparse


HOST = "0.0.0.0"
PORT = 8080


def recv_some(sock):
    """Read up to 4 KiB from the socket. Empty bytes means EOF."""
    return sock.recv(4096)


def parse_request(raw):
    """
    Parse one HTTP/1.1 request from raw bytes.
    Returns None if incomplete, else a dict with method/path/query/headers/consumed.
    On parse failure, consumed is still set so the caller can advance the buffer.
    """
    header_end = raw.find(b"\r\n\r\n")
    if header_end == -1:
        return None

    header_block = raw[:header_end]
    consumed_base = header_end + 4

    try:
        header_text = header_block.decode("ascii")
    except UnicodeDecodeError:
        return {"error": "bad_encoding", "consumed": consumed_base}

    lines = header_text.split("\r\n")
    if not lines:
        return {"error": "empty", "consumed": consumed_base}

    request_line = lines[0]
    parts = request_line.split(" ")
    if len(parts) != 3:
        return {"error": "bad_request_line", "consumed": consumed_base}

    method, target, version = parts
    if version != "HTTP/1.1":
        return {"error": "bad_version", "consumed": consumed_base}

    parsed_url = urlparse(target)
    path = parsed_url.path
    query = parse_qs(parsed_url.query, keep_blank_values=True)

    headers = {}
    for line in lines[1:]:
        if not line:
            continue
        if ":" not in line:
            return {"error": "bad_header", "consumed": consumed_base}
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    try:
        content_length = int(headers.get("content-length", "0"))
    except ValueError:
        return {"error": "bad_content_length", "consumed": consumed_base}

    if content_length < 0:
        return {"error": "bad_content_length", "consumed": consumed_base}

    total_needed = consumed_base + content_length
    if len(raw) < total_needed:
        return None  # still waiting for body bytes

    return {
        "method": method,
        "path": path,
        "query": query,
        "headers": headers,
        "consumed": total_needed,
    }


def parse_int_param(query, name):
    """Return int value for query param, 'invalid', or None if missing."""
    values = query.get(name)
    if not values:
        return None
    try:
        return int(values[0])
    except ValueError:
        return "invalid"


def compute(path, query):
    """Run calculator logic. Returns (status_code, status_text, body_str)."""
    ops = {
        "/add": lambda a, b: a + b,
        "/sub": lambda a, b: a - b,
        "/mul": lambda a, b: a * b,
        "/div": lambda a, b: a // b if a % b == 0 else a / b,
    }

    if path not in ops:
        return 404, "Not Found", ""

    a = parse_int_param(query, "a")
    b = parse_int_param(query, "b")
    if a == "invalid" or b == "invalid" or a is None or b is None:
        return 400, "Bad Request", ""

    if path == "/div" and b == 0:
        return 400, "Bad Request", ""

    result = ops[path](a, b)
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return 200, "OK", str(result)


def build_response(status_code, status_text, body):
    """Build a minimal HTTP/1.1 response with Content-Length."""
    body_bytes = body.encode("ascii") if body else b""
    header = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "Connection: keep-alive\r\n"
        "Content-Type: text/plain\r\n"
        "\r\n"
    ).encode("ascii")
    return header + body_bytes


def handle_request(parsed):
    """Turn a parsed request dict into response bytes."""
    if "error" in parsed:
        return build_response(400, "Bad Request", "")

    if "host" not in parsed["headers"]:
        return build_response(400, "Bad Request", "")

    if parsed["method"] != "GET":
        return build_response(405, "Method Not Allowed", "")

    status, text, body = compute(parsed["path"], parsed["query"])
    return build_response(status, text, body)


def serve_client(conn):
    """Handle many requests on one persistent connection."""
    buffer = b""

    while True:
        # Read until we can parse one full request (headers + Content-Length body).
        while True:
            parsed = parse_request(buffer)
            if parsed is not None:
                break
            chunk = recv_some(conn)
            if not chunk:
                return
            buffer += chunk

        consumed = parsed["consumed"]
        response = handle_request(parsed)
        conn.sendall(response)
        buffer = buffer[consumed:]


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, port))
        server.listen(5)
        print(f"Calculator server listening on {HOST}:{port}")

        while True:
            conn, addr = server.accept()
            print(f"Connection from {addr}")
            try:
                serve_client(conn)
            except (ConnectionResetError, BrokenPipeError):
                pass
            finally:
                conn.close()


if __name__ == "__main__":
    main()
