# CML Orchestrator Documentation

A minimal Django app to orchestrate a pool of Cisco CML (Cisco Modeling Labs) servers for students. It provides:

- Web UI for admins to manage controllers and assignments
- Background worker for health checks and lease cleanup
- Small API to assign a user to a lab and to release
- Bulk lab YAML upload with duplicate cleanup
- Pool metrics snapshots for availability trends

Quick links:
- Setup: docs/setup.md
- Configuration (env vars): docs/configuration.md
- Usage (web UI): docs/usage.md
- API reference: docs/api.md
- Background worker: docs/worker.md
- Security notes: docs/security.md

## Quickstart

- Requirements: Python 3.11+ recommended, pip, virtualenv
- Create and activate a virtualenv, then install Django and WhiteNoise:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install "Django>=4.2" whitenoise`
- Copy `./.env.example` to `./.env` and edit as needed.
- Initialize DB and admin user:
  - `python manage.py migrate`
  - `python manage.py createsuperuser`
- Run dev server: `python manage.py runserver 0.0.0.0:8005`
- Or run with Gunicorn:
  - `gunicorn cmlorc.wsgi:application --workers 5 --bind 0.0.0.0:8005 --log-level info`

Notes:
- For production, run `python manage.py collectstatic` and serve via WhiteNoise (enabled here) or a CDN.
- The background worker runs during `runserver`. In production you can set `RUN_BACKGROUND_WORKER=1` on one process, or run it via `python manage.py runhealthworker`.

