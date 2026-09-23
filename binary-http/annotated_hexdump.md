# Annotated Hexdump — One Complete BCP1 Exchange

Captured from `./bserve www 9000` and a client request for `/about.txt`.

**Scenario:** Client opens TCP to `localhost:9000`, sends one REQUEST frame, receives one RESPONSE frame. Connection remains open.

---

## REQUEST (client → server, 39 bytes total)

```
Offset   Hex                                         ASCII
------   -----------------------------------------   ----------------
00000000  42 43 50 31 01 01 00 00 00 00 00 1b        BCP1........
0000000c  01 00 0a 2f 61 62 6f 75 74 2e 74 74 78      .../about.txt
00000018  01 02 00 09 6c 6f 63 61 6c 68 6f 73 74 00  ....localhost.
```

### Frame header (bytes 0–11)

| Bytes | Value | Meaning |
|-------|-------|---------|
| `42 43 50 31` | `"BCP1"` | Magic — identifies the protocol |
| `01` | 1 | Protocol version |
| `01` | 0x01 | Frame type: **REQUEST** |
| `00 00` | 0 | Flags (reserved) |
| `00 00 00 1b` | 27 | Payload length: 27 bytes follow |

### REQUEST payload (bytes 12–38)

| Bytes | Value | Meaning |
|-------|-------|---------|
| `01` | 1 | Method: **GET** |
| `00 0a` | 10 | Path length |
| `2f 61 62 6f 75 74 2e 74 74 78` | `/about.txt` | Request path (UTF-8) |
| `01` | 1 | **1** indexed header follows |
| `02` | 2 | Index 2 → header name **`host`** (static table) |
| `00 09` | 9 | Value length |
| `6c 6f 63 61 6c 68 6f 73 74` | `localhost` | Host value |
| `00` | 0 | **0** dynamic headers |

---

## RESPONSE (server → client, 97 bytes total)

```
Offset   Hex                                         ASCII
------   -----------------------------------------   ----------------
00000000  42 43 50 31 01 02 00 00 00 00 00 55        BCP1.......U
0000000c  00 c8 00 00 00 00 00 4d 42 43 50 31 20 66  .......MBCP1 f
00000018  69 6c 65 20 73 65 72 76 65 72 20 64 65 6d  ile server dem
00000024  6f 2e 0a 4f 6e 65 20 54 43 50 20 63 6f 6e 6e  o..One TCP conn
00000030  65 63 74 69 6f 6e 2c 20 62 69 6e 61 72 79 20  ection, binary 
0000003c  66 72 61 6d 65 73 2c 20 70 65 72 73 69 73 74  frames, persist
00000048  65 6e 74 20 73 6f 63 6b 65 74 2e 0a           ent socket..
```

### Frame header (bytes 0–11)

| Bytes | Value | Meaning |
|-------|-------|---------|
| `42 43 50 31` | `"BCP1"` | Magic |
| `01` | 1 | Version |
| `02` | 0x02 | Frame type: **RESPONSE** |
| `00 00` | 0 | Flags |
| `00 00 00 55` | 85 | Payload length |

### RESPONSE payload (bytes 12–96)

| Bytes | Value | Meaning |
|-------|-------|---------|
| `00 c8` | 200 | HTTP-style status **200 OK** |
| `00` | 0 | Zero indexed headers in this response |
| `00` | 0 | Zero dynamic headers |
| `00 00 00 4d` | 77 | Body length (decimal) |
| `42 43 50 31 20 66 69 6c 65...` | (text) | File contents of `about.txt` |

Body decoded:

```
BCP1 file server demo.
One TCP connection, binary frames, persistent socket.
```

---

## What this demonstrates

1. **Framing:** Each message starts with a 12-byte header; `Length` tells you exactly how many payload bytes belong to this frame — byte *n+1* of the next frame is not read until those bytes are consumed.
2. **Persistent TCP:** Neither side closes the socket after this exchange; the server loop waits for another frame.
3. **Indexed headers:** The client sends `host` as index `2` plus a length-prefixed value instead of spelling out the name on the wire.
4. **Status + body:** The response carries a 16-bit status, optional headers, a 32-bit body length, then raw bytes.

Raw hex (single line, for scripts):

```
REQUEST:  42435031010100000000001b01000a2f61626f75742e747874010200096c6f63616c686f737400
RESPONSE: 42435031010200000000005500c800000000004d424350312066696c65207365727665722064656d6f2e0a4f6e652054435020636f6e6e656374696f6e2c2062696e617279206672616d65732c2070657273697374656e7420736f636b65742e0a
```
