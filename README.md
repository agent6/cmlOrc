# CML Orchestrator

Minimal Django app to orchestrate a pool of Cisco CML servers for students.

## Run The Server

Start with Gunicorn on port 8005:

```
gunicorn cmlorc.wsgi:application --workers 5 --bind 0.0.0.0:8005 --log-level info
```

## Simple API

### Assign User to Lab and return Server IP

- Endpoint: `POST /api/assign/`
- Accepts: JSON (`application/json`) or form-encoded (`application/x-www-form-urlencoded`)
- Parameters:
  - `username` or `user`: username to assign
  - `lab` or `lab_name`: target lab name or UUID
  - `minutes` (optional): lease duration in minutes (default 240)
- Behavior:
  - Creates the user if they do not exist (non-staff, unusable password).
  - Assigns via the pool (reuses current assignment or picks the first healthy available server).
  - If the same user re-assigns to the same lab, extends the lease only (does not reset/wipe).
- Response:
  - 200: plain text body containing the server IP address
  - 4xx/5xx: JSON error payload `{ "error": "message" }`

Examples:

Form-encoded:

```
curl -sS -X POST http://localhost:8005/api/assign/ -d 'user=student05&lab=Lab1'
```

JSON:

```
curl -sS -X POST http://localhost:8005/api/assign/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"student05","lab":"Lab1","minutes":120}'
```

### Release User Assignment

- Endpoint: `POST /api/release/`
- Accepts: JSON (`application/json`) or form-encoded (`application/x-www-form-urlencoded`)
- Parameters:
  - `username` or `user`: username whose assignment should be released
- Behavior:
  - If the user has an assigned CML server, it clears the assignment immediately and triggers a best‑effort background cleanup (stop/wipe labs).
  - If the user has no assignment, it returns a no‑op indicator.
- Response:
  - 200: plain text `OK` if released, or `NONE` if no assignment exists
  - 4xx/5xx: JSON error payload `{ "error": "message" }`

Examples:

Form-encoded:

```
curl -sS -X POST http://localhost:8005/api/release/ -d 'user=student05'
```

JSON:

```
curl -sS -X POST http://localhost:8005/api/release/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"student05"}'
```

Note: For production, protect these endpoints with auth (session, token, or network boundary).
