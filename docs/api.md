# API Reference

The API is intentionally minimal and designed to be fronted by your own auth or a network boundary. Endpoints accept `application/json` or `application/x-www-form-urlencoded`.

## Assign User to Lab and return Controller IP

- Endpoint: `POST /api/assign/`
- Params:
  - `username` or `user`: required
  - `lab` or `lab_name`: required (CML lab title or UUID)
  - `minutes`: optional integer, default 60
- Behavior:
  - User is created if missing (non-staff, unusable password).
  - Uses pool assignment (reuse existing assignment; otherwise first healthy available).
  - If same user + same lab on same server, only extends the lease.
- Response:
  - 200 OK: text/plain body with controller IP address
  - 4xx/5xx: JSON `{ "error": "message" }`

Examples:

Form:
```
curl -sS -X POST http://localhost:8005/api/assign/ -d 'user=student05&lab=Lab1'
```

JSON:
```
curl -sS -X POST http://localhost:8005/api/assign/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"student05","lab":"Lab1","minutes":60}'
```

## Release User Assignment

- Endpoint: `POST /api/release/`
- Params:
  - `username` or `user`: required
- Response:
  - 200 OK: `OK` if released, `NONE` if no assignment
  - 4xx/5xx: JSON `{ "error": "message" }`

Example:
```
curl -sS -X POST http://localhost:8005/api/release/ -d 'user=student05'
```

Security: These endpoints are unauthenticated by default. Protect with network rules, a reverse proxy, or extend them to require auth tokens.
