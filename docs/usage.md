# Usage (Web UI)

- Login: Visit `/login/` and authenticate with a Django superuser or staff account.
- Home: Lists all CML servers, their status and current assignments.

Server actions:
- Add Server: Provide base API URL (e.g., `https://host/api/v0`), username, password, and TLS verify preference. The app probes health immediately.
- Edit/Clone: Update credentials or clone from an existing server.
- Test: Performs an auth + list and a health probe; updates status.
- Assign: Assign a user to a lab by name/UUID and set lease minutes. If the same user reassigns the same lab on the same server, only the lease is extended.
- Release: Clears assignment and schedules background cleanup (stop/wait/wipe other labs).
- Delete: Removes the server record.

Pool actions:
- Assign Student to Lab: Assign via pool — reuses a user’s existing assignment or picks the first healthy available controller.
- Upload Lab YAML to All: Upload a CML lab YAML to every controller. Titles are detected; existing labs with the same title are stopped, wiped, and deleted before import to avoid duplicates.
- Health Settings: Tune health mode, intervals, retries, backoff, and stats snapshot frequency.
- Pool Metrics: Shows time series snapshots (requires the `PoolStat` table; created by migrations, or will attempt on first use).

Tips:
- Base URL normalization: The app tries to ensure base URLs include `/api/v0`.
- TLS verify: You can disable verification for dev/self-signed controllers; enable it in production.

