# Configuration

Environment variables consumed by the app (defaults shown):

- `DJANGO_SECRET_KEY`:
  - Secret for Django. Default: `dev-insecure-secret-key-change-me`.
  - Set a long random value in production.
- `DJANGO_DEBUG`:
  - `1` enables debug; `0` disables. Default: `1`.
- `TZ`:
  - Server timezone. Default: `UTC`.
- `RUN_BACKGROUND_WORKER`:
  - `1` runs the background health/lease worker in-process (e.g., inside one Gunicorn worker). Default: `0`.
- `HEALTH_CHECK_INTERVAL`:
  - Seconds between normal health checks. Default: `30`.
- `HEALTH_SCHEDULER_TICK`:
  - Sleep between scheduler iterations. Default: `1`.
- `HEALTH_CHECK_HTTP_TIMEOUT`:
  - HTTP timeout for health probes (seconds). Default: `12`.
- `HEALTH_CHECK_BACKOFF_BASE`:
  - Base backoff after a confirmed failure (seconds). Default: `15`.
- `HEALTH_CHECK_BACKOFF_MAX`:
  - Max backoff cap (seconds). Default: `300`.
- `IMPORT_HTTP_TIMEOUT`:
  - HTTP timeout for lab YAML imports (seconds). Default: `8`.

Notes:
- `ALLOWED_HOSTS` is set to `*` in `cmlorc/settings.py` for convenience. For production, restrict it to known hosts/IPs.
- Health behavior can also be tuned at runtime in the UI at `/settings/health/` (stored in the `HealthSettings` model).

