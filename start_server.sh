#!/usr/bin/env bash
# start_server.sh — Kill port 8005, run Django maintenance, and start Gunicorn

set -euo pipefail

PORT=8005
HOST="0.0.0.0"
APP="cmlorc.wsgi:application"
WORKERS="${WORKERS:-5}"                 # override: WORKERS=8 ./start_server.sh
PYTHON_BIN="${PYTHON_BIN:-python3}"     # override: PYTHON_BIN=/path/to/python ./start_server.sh
LOG_DIR="${LOG_DIR:-./logs}"
STDOUT_LOG="${LOG_DIR}/gunicorn.out"
STDERR_LOG="${LOG_DIR}/gunicorn.err"
PID_FILE="${LOG_DIR}/gunicorn.pid"

cd "$(dirname "$0")"

# Optional: activate a virtualenv if present
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

# Basic sanity checks
command -v "${PYTHON_BIN}" >/dev/null 2>&1 || { echo "ERROR: ${PYTHON_BIN} not found."; exit 1; }
command -v gunicorn >/dev/null 2>&1 || { echo "ERROR: gunicorn not found. Try: pip install gunicorn"; exit 1; }
[[ -f "manage.py" ]] || { echo "ERROR: manage.py not found in $(pwd)"; exit 1; }

mkdir -p "${LOG_DIR}"

echo ">> Killing anything bound to port ${PORT}..."
# Try fuser, then lsof; first TERM, then KILL as fallback
(fuser -k "${PORT}"/tcp 2>/dev/null || true)
(lsof -ti:"${PORT}" | xargs -r kill 2>/dev/null || true)
sleep 0.3
(lsof -ti:"${PORT}" | xargs -r kill -9 2>/dev/null || true)
sleep 0.5

# If a stale PID file exists, try to stop that process too
if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}" || true)"
  if [[ -n "${OLD_PID:-}" ]]; then
    kill "${OLD_PID}" 2>/dev/null || true
    sleep 0.2
    kill -9 "${OLD_PID}" 2>/dev/null || true
  fi
  rm -f "${PID_FILE}"
fi

echo ">> Running Django maintenance tasks..."
${PYTHON_BIN} manage.py makemigrations --noinput
${PYTHON_BIN} manage.py migrate --noinput
${PYTHON_BIN} manage.py collectstatic --noinput --clear

echo ">> Starting Gunicorn (${WORKERS} workers) on ${HOST}:${PORT}..."
# nohup keeps it running after shell exits; logs go to files
nohup gunicorn "${APP}" \
  --workers "${WORKERS}" \
  --bind "${HOST}:${PORT}" \
  --log-level info \
  --pid "${PID_FILE}" \
  > "${STDOUT_LOG}" 2> "${STDERR_LOG}" &

PID=$!
echo ">> Gunicorn started (launcher PID ${PID})."
echo ">> Logs: ${STDOUT_LOG} (stdout), ${STDERR_LOG} (stderr)"
echo ">> PID file: ${PID_FILE}"
echo ">> Done."
