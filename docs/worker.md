# Background Worker

Purpose:
- Periodically probe controller health with tunable mode (lightweight ping vs full lab list).
- Confirm failures with quick retries; apply exponential backoff.
- Release expired leases and record pool metrics snapshots.

How it runs:
- Dev: auto-starts during `runserver` via `orchestrator.apps.OrchestratorConfig.ready()`.
- Prod: either set `RUN_BACKGROUND_WORKER=1` for one process (uses a file lock in `/tmp` to ensure one instance), or run externally:
  - `python manage.py runhealthworker`

Tuning:
- Environment defaults in `cmlorc/settings.py` (see docs/configuration.md).
- At runtime via the UI at `/settings/health/` (`HealthSettings` model).

Notes:
- The file lock uses `fcntl` (POSIX). On Windows, prefer a separate worker process.
- Snapshots go into `PoolStat`; the UI charts read from that table.

