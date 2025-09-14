#!/usr/bin/env python3
import os
import sys
try:
    from cmlorc.env import load_env
    load_env()
except Exception:
    pass


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cmlorc.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and available on your PYTHONPATH?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

