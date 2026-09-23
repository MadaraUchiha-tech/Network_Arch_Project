# BCP1 — Binary Campus Protocol v1

**Authors:** Network Architecture assignment submission  
**Transport:** TCP (persistent connection — do not close after one exchange)  
**Byte order:** Big-endian unless noted

This document describes a minimal binary request/response protocol inspired by HTTP/2 framing and HPACK header compression. A reader who has only this spec should be able to implement a compatible client or server.

---

## 1. Connection model

1. Client opens **one** TCP connection to the server.
2. Communication is a sequence of **frames**. Each frame has a fixed 12-byte header followed by a payload.
3. After sending a response, the **server keeps the connection open** and waits for another frame.
4. The client **must not** open a second connection for follow-up requests on the same session (bcurl opens one socket per invocation, which is one fetch).

**Ambiguity note:** We only define GET for file fetch. POST/PUT are reserved for future versions.

---

## 2. Frame header (12 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | Magic | Literal bytes `42 43 50 31` (`"BCP1"`) |
| 4 | 1 | Version | Must be `1` |
| 5 | 1 | Type | Frame type (see §3) |
| 6 | 2 | Flags | Reserved; send `0`, ignore on receive |
| 8 | 4 | Length | Payload length in bytes (may be 0) |

If Magic or Version is wrong, the receiver **must** close the connection with an error.

---

## 3. Frame types

| Value | Name | Direction | Description |
|-------|------|-----------|-------------|
| `0x01` | REQUEST | client → server | Fetch a file |
| `0x02` | RESPONSE | server → client | Status, headers, body |
| *other* | — | either | **Must be skipped** (see §7) |

---

## 4. REQUEST payload (Type = 0x01)

| Field | Size | Description |
|-------|------|-------------|
| Method | 1 | `1` = GET (only method defined in v1) |
| PathLen | 2 | Length of path in bytes |
| Path | PathLen | UTF-8 path, must start with `/` (e.g. `/index.html`) |
| Header block | variable | Encoded as §6 |

Unknown methods → server responds with **400**.

---

## 5. RESPONSE payload (Type = 0x02)

| Field | Size | Description |
|-------|------|-------------|
| Status | 2 | `200` OK, `400` bad request, `404` not found |
| Header block | variable | Encoded as §6 |
| BodyLen | 4 | Length of body |
| Body | BodyLen | Raw file bytes (empty for errors) |

Status codes ≥ 400 mean failure; bcurl exits non-zero.

---

## 6. Header block (HPACK-style, simplified)

Two kinds of headers, sent in order:

### 6.1 Indexed headers

| Field | Size |
| NumIndexed | 1 | Count of indexed entries (0–255) |
| For each entry: | |
| → Index | 1 | 1–10 (static table below) |
| → ValueLen | 2 | Length of value |
| → Value | ValueLen | UTF-8 string |

**Static table (index → name):**

| Index | Name |
|-------|------|
| 1 | `:path` |
| 2 | `host` |
| 3 | `accept` |
| 4 | `user-agent` |
| 5 | `accept-encoding` |
| 6 | `connection` |
| 7 | `cache-control` |
| 8 | `if-modified-since` |
| 9 | `referer` |
| 10 | `authorization` |

The path is already in the REQUEST frame; index 1 is optional. Index 2 (`host`) should carry the hostname.

### 6.2 Dynamic headers (length-prefixed names)

| Field | Size |
| NumDynamic | 1 | Count (0–255) |
| For each entry: | |
| → NameLen | 1 | 1–255 |
| → Name | NameLen | UTF-8 header name |
| → ValueLen | 2 | Length of value |
| → Value | ValueLen | UTF-8 value |

---

## 7. Forward compatibility

If a receiver reads a frame whose **Type** is not `0x01` or `0x02`:

1. Read exactly **Length** bytes of payload (may be zero).
2. Discard them.
3. Read the next frame header.

This allows future extensions (e.g. `0x03` PING) without breaking v1 implementations.

Malformed frames (truncated payload, bad header block) → **400** response if possible, else close connection.

---

## 8. File mapping (server)

Command: `./bserve <webroot> <port>`

- Request path `/index.html` maps to `<webroot>/index.html`.
- Path must start with `/`. `..` segments are rejected → **400**.
- Missing file → **404**.
- Only regular files are served.

---

## 9. Client behaviour

Command: `./bcurl [-v] host:port/path`

- Builds one REQUEST frame, sends on one TCP connection.
- Reads frames until a RESPONSE (`0x02`) is received (skipping unknown types).
- Prints body to stdout on **200**.
- `-v`: hexdump every frame sent and received.
- Exit code **1** on 4xx/5xx or protocol error.

Target parsing: split on first `/` → `host:port` + `/path`. Default port **80** if omitted.

---

## 10. Example exchange (summary)

```
Client  --[REQUEST  GET /index.html, host=localhost]-->  Server
Client  <--[RESPONSE 200, body=<file bytes>]----------  Server
(connection stays open)
```

See `annotated_hexdump.md` for a byte-level walkthrough of one complete request and response.
