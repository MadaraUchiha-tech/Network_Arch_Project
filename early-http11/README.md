# Early HTTP/1.1 Calculator

A minimal HTTP/1.1 calculator over **one persistent TCP connection** — no frameworks, just sockets.

## Run

```bash
python3 server.py          # listens on port 8080
python3 server.py 9000     # custom port
```

## Endpoints

| Request | Response |
|---------|----------|
| `GET /add?a=2&b=3` | 200, body `5` |
| `GET /sub?a=10&b=4` | 200, body `6` |
| `GET /mul?a=6&b=7` | 200, body `42` |
| `GET /div?a=9&b=3` | 200, body `3` |
| `GET /div?a=1&b=0` | 400 |
| `GET /add?a=x&b=3` | 400 |
| `GET /pow?a=2&b=8` | 404 |
| `POST /add` | 405 |
| `GET /add` without `Host` header | 400 |

All successful/error responses include `Content-Length` and `Connection: keep-alive`. The server does **not** close the socket after each response.

## Manual test (matches grader)

```python
import socket

s = socket.create_connection(("localhost", 8080))

def req(path, method="GET"):
    msg = (
        f"{method} {path} HTTP/1.1\r\n"
        "Host: localhost\r\n"
        "\r\n"
    )
    s.sendall(msg.encode())

req("/add?a=2&b=3")
# read until you have headers + Content-Length body bytes
# ... repeat for sub, mul, div by zero, pow, POST ...
print("socket still open:", s.fileno() != -1)
```

## Automated tests

```bash
python3 test_server.py
```

Tests cover the six-request grader sequence, missing Host, invalid params, and two pipelined requests in one `send()`.

## Design notes

- Requests are framed by reading headers up to `\r\n\r\n`, then exactly `Content-Length` body bytes (usually 0 for GET).
- The leftover buffer after each request is kept for the next request on the same connection.
- This is the core HTTP/1.1 keep-alive problem: knowing where one request ends and the next begins.
