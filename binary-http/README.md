# BCP1 — Binary HTTP Assignment

Custom binary protocol with persistent TCP, plus `bserve` (server) and `bcurl` (client).

## Files

| File | Purpose |
|------|---------|
| `protocol_spec.md` | Two-page protocol specification |
| `annotated_hexdump.md` | Labelled byte dump of one request/response |
| `protocol.py` | Shared frame encode/decode |
| `bserve` | File server |
| `bcurl` | File fetch client |
| `www/` | Sample web root |

## Run

Terminal 1:

```bash
./bserve ./www 9000
```

Terminal 2:

```bash
./bcurl localhost:9000/index.html
./bcurl -v localhost:9000/about.txt   # hexdump frames
```

`bcurl` exits with code 1 on 4xx/5xx.

## Tests

```bash
python3 test_binary.py
```

Covers file fetch, 404, two requests on one socket, unknown-frame skipping, malformed request → 400, and `-v` output.

## Protocol summary

- 12-byte frame header: magic `BCP1`, version, type, flags, payload length
- Types: `0x01` REQUEST, `0x02` RESPONSE; unknown types are skipped
- HPACK-style headers: 10 indexed names + length-prefixed dynamic headers
- Connection stays open after each response

See `protocol_spec.md` for full details.
