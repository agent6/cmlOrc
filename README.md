# CML Orchestrator

Minimal Django app to orchestrate a pool of Cisco CML servers for students.

Documentation: docs/README.md

## Get The Code

- Clone the repo:
  - `git clone https://github.com/agent6/cmlOrc.git`
  - `cd cmlOrc`
- To update later:
  - `git pull`

## Run The Server

Development:
- `python -m venv .venv && source .venv/bin/activate`
- `python -m pip install -U pip wheel`
- Install deps: `pip install -r requirements.txt`
- Copy `.env.example` to `.env` and edit it.
- Initialize DB: `python manage.py migrate`
- Create admin: `python manage.py createsuperuser`
- Start: `python manage.py runserver 0.0.0.0:8005`

Production (example):
- Install deps: `python -m pip install -r requirements.txt`
- Collect static: `python manage.py collectstatic --noinput --clear`
- Run app: `gunicorn cmlorc.wsgi:application --workers 5 --bind 0.0.0.0:8005 --log-level info`

Notes:
- A tiny `.env` loader is included; if a `.env` file exists, it is loaded automatically.
- The background worker auto-runs during `runserver`. In production, either set `RUN_BACKGROUND_WORKER=1` for one process, or run `python manage.py runhealthworker` as a separate service.

## Simple API

### Assign User to Lab and return Server IP

- Endpoint: `POST /api/assign/`
- Accepts: JSON (`application/json`) or form-encoded (`application/x-www-form-urlencoded`)
- Parameters:
  - `username` or `user`: username to assign
  - `lab` or `lab_name`: target lab name or UUID
  - `minutes` (optional): lease duration in minutes (default 60)
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
  -d '{"username":"student05","lab":"Lab1","minutes":60}'
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

## Static Files

- Source assets live in `static/` (you edit these).
- Collected assets are written to `staticfiles/` by `collectstatic` (hashed, gzipped). This folder is generated at build/deploy and is ignored by git.
- WhiteNoise is enabled and configured to keep only hashed files. Templates reference logical paths (e.g., `{% static 'styles/darkmode.css' %}`) which resolve to the latest hashed asset via the manifest.
- To refresh static output, run: `python manage.py collectstatic --noinput --clear`.

Favicon
- A placeholder favicon is provided at `static/favicon.png`. The base template links it, and `/favicon.ico` is routed to it.
