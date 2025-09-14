import os
try:
    from .env import load_env
    load_env()
except Exception:
    pass
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cmlorc.settings")

application = get_wsgi_application()

