# Network Architecture — Assignment Submissions

Two related socket programming assignments demonstrating persistent TCP connections and request framing.

## 1. Early HTTP/1.1 Calculator (`early-http11/`)

Text-based HTTP/1.1 calculator on port 8080. One socket, many requests.

```bash
cd early-http11
python3 server.py
python3 test_server.py
```

## 2. Binary Protocol (`binary-http/`)

Custom BCP1 binary protocol with file server and client.

```bash
cd binary-http
./bserve ./www 9000
./bcurl -v localhost:9000/index.html
python3 test_binary.py
```

Deliverables: `protocol_spec.md`, `annotated_hexdump.md`, `bserve`, `bcurl`.

Both projects use plain Python 3 and the standard library only — no web frameworks.
