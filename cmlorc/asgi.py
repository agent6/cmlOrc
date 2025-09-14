import os
try:
    from .env import load_env
    load_env()
except Exception:
    pass
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cmlorc.settings")

application = get_asgi_application()

