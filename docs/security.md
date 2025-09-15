# Security Notes

- API endpoints (`/api/assign/`, `/api/release/`) are unauthenticated by default; deploy behind a trusted network boundary or add authentication/authorization before exposing.
- `ALLOWED_HOSTS` is currently `*` for convenience. Restrict it for production.
- CML controller credentials are stored in the database. Limit access to the admin UI, database, and server filesystem appropriately.
- TLS verification is configurable per controller. Use `verify_tls=True` for production controllers.
- If you run the background worker in-process, ensure only one instance is active (the app uses a lock). Alternatively, run as a separate process.

