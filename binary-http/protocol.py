"""
BCP1 — Binary Campus Protocol v1

Shared frame encoding/decoding used by bserve and bcurl.
See protocol_spec.md for the full specification.
"""

import struct

MAGIC = b"BCP1"
VERSION = 1

# Frame types
FRAME_REQUEST = 0x01
FRAME_RESPONSE = 0x02

# Methods
METHOD_GET = 1

# Indexed header names (HPACK-style static table, 1-based)
INDEXED_HEADERS = {
    1: ":path",
    2: "host",
    3: "accept",
    4: "user-agent",
    5: "accept-encoding",
    6: "connection",
    7: "cache-control",
    8: "if-modified-since",
    9: "referer",
    10: "authorization",
}

HEADER_NAME_TO_INDEX = {v: k for k, v in INDEXED_HEADERS.items()}

FRAME_HEADER_SIZE = 12
FRAME_HEADER_FMT = ">4sBBH I"  # magic, version, type, flags, length


class ProtocolError(Exception):
    pass


def hexdump(data, prefix="", label=""):
    """Print a simple hexdump for -v mode."""
    lines = []
    if label:
        lines.append(label)
    for i in range(0, len(data), 16):
        chunk = data[i : i + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{prefix}{i:08x}  {hex_part:<48}  {ascii_part}")
    return "\n".join(lines)


def encode_frame(frame_type, payload, flags=0):
    """Wrap payload in a BCP1 frame header."""
    if len(payload) > 0xFFFFFFFF:
        raise ProtocolError("payload too large")
    header = struct.pack(
        FRAME_HEADER_FMT,
        MAGIC,
        VERSION,
        frame_type,
        flags,
        len(payload),
    )
    return header + payload


def read_exact(sock, n):
    """Read exactly n bytes from a socket."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ProtocolError("unexpected EOF")
        buf += chunk
    return buf


def read_frame(sock):
    """
    Read one frame from the socket.
    Unknown frame types are skipped (forward compatibility).
    Returns (frame_type, payload) for known types.
    """
    while True:
        header = read_exact(sock, FRAME_HEADER_SIZE)
        magic, version, frame_type, flags, length = struct.unpack(
            FRAME_HEADER_FMT, header
        )

        if magic != MAGIC:
            raise ProtocolError("bad magic bytes")
        if version != VERSION:
            raise ProtocolError(f"unsupported version {version}")

        payload = read_exact(sock, length) if length else b""

        if frame_type in (FRAME_REQUEST, FRAME_RESPONSE):
            return frame_type, payload
        # Unknown type: skip payload cleanly and read next frame.


def encode_headers(indexed=None, dynamic=None):
    """
    Encode header block.
    indexed: list of (index, value_str)
    dynamic: list of (name_str, value_str)
    """
    indexed = indexed or []
    dynamic = dynamic or []
    out = bytearray()
    out.append(len(indexed))
    for idx, value in indexed:
        out.append(idx)
        vb = value.encode("utf-8")
        out.extend(struct.pack(">H", len(vb)))
        out.extend(vb)
    out.append(len(dynamic))
    for name, value in dynamic:
        nb = name.encode("utf-8")
        vb = value.encode("utf-8")
        if len(nb) > 255:
            raise ProtocolError("header name too long")
        out.append(len(nb))
        out.extend(nb)
        out.extend(struct.pack(">H", len(vb)))
        out.extend(vb)
    return bytes(out)


def decode_headers(data, offset=0):
    """Decode header block. Returns (indexed_list, dynamic_list, new_offset)."""
    if offset >= len(data):
        raise ProtocolError("truncated header block")

    num_indexed = data[offset]
    offset += 1
    indexed = []
    for _ in range(num_indexed):
        idx = data[offset]
        offset += 1
        (vlen,) = struct.unpack(">H", data[offset : offset + 2])
        offset += 2
        value = data[offset : offset + vlen].decode("utf-8")
        offset += vlen
        indexed.append((idx, value))

    num_dynamic = data[offset]
    offset += 1
    dynamic = []
    for _ in range(num_dynamic):
        nlen = data[offset]
        offset += 1
        name = data[offset : offset + nlen].decode("utf-8")
        offset += nlen
        (vlen,) = struct.unpack(">H", data[offset : offset + 2])
        offset += 2
        value = data[offset : offset + vlen].decode("utf-8")
        offset += vlen
        dynamic.append((name, value))

    return indexed, dynamic, offset


def encode_request(method, path, indexed=None, dynamic=None):
    """Build a REQUEST frame payload."""
    pb = path.encode("utf-8")
    payload = bytearray()
    payload.append(method)
    payload.extend(struct.pack(">H", len(pb)))
    payload.extend(pb)
    payload.extend(encode_headers(indexed, dynamic))
    return encode_frame(FRAME_REQUEST, bytes(payload))


def decode_request(payload):
    """Parse REQUEST frame payload."""
    if len(payload) < 3:
        raise ProtocolError("request too short")
    method = payload[0]
    (path_len,) = struct.unpack(">H", payload[1:3])
    offset = 3
    path = payload[offset : offset + path_len].decode("utf-8")
    offset += path_len
    indexed, dynamic, offset = decode_headers(payload, offset)
    return {"method": method, "path": path, "indexed": indexed, "dynamic": dynamic}


def encode_response(status, body, indexed=None, dynamic=None):
    """Build a RESPONSE frame payload."""
    body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
    payload = bytearray()
    payload.extend(struct.pack(">H", status))
    payload.extend(encode_headers(indexed, dynamic))
    payload.extend(struct.pack(">I", len(body_bytes)))
    payload.extend(body_bytes)
    return encode_frame(FRAME_RESPONSE, bytes(payload))


def decode_response(payload):
    """Parse RESPONSE frame payload."""
    if len(payload) < 6:
        raise ProtocolError("response too short")
    (status,) = struct.unpack(">H", payload[0:2])
    indexed, dynamic, offset = decode_headers(payload, 2)
    (body_len,) = struct.unpack(">I", payload[offset : offset + 4])
    offset += 4
    body = payload[offset : offset + body_len]
    if len(body) != body_len:
        raise ProtocolError("truncated body")
    return {
        "status": status,
        "indexed": indexed,
        "dynamic": dynamic,
        "body": body,
    }
