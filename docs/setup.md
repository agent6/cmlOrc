# Setup

# Setup

## Get the code

- Clone the repo and enter the project directory:
  - `git clone https://github.com/agent6/cmlOrc.git`
  - `cd cmlOrc`

Prerequisites:
- Python 3.11+
- pip and virtualenv recommended

Steps:
- Create a virtualenv and install dependencies:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install "Django>=4.2" whitenoise`
- Copy `.env.example` to `.env` and edit values (see docs/configuration.md).
- Initialize the database and create an admin user:
  - `python manage.py migrate`
  - `python manage.py createsuperuser`
- Development server:
  - `python manage.py runserver 0.0.0.0:8005`
- Production (example):
  - `python -m pip install gunicorn`
  - `python manage.py collectstatic --noinput`
  - `gunicorn cmlorc.wsgi:application --workers 5 --bind 0.0.0.0:8005 --log-level info`

Notes:
- This project includes a tiny `.env` loader (`cmlorc/env.py`). If a `.env` exists in the repo root, it will be loaded automatically by `manage.py` and `wsgi.py`.
- SQLite is used by default. For production, consider configuring Postgres and updating `DATABASES` in `cmlorc/settings.py`.

## Updating to the latest version

- Pull changes from the remote:
  - `git pull`
