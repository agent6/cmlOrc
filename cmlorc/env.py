import os
from pathlib import Path


def load_env(path: str | None = None) -> None:
    """Very small .env loader with no third-party dependency.
    - Reads KEY=VALUE lines from .env in repo root by default
    - Ignores comments and blank lines
    - Does not override existing environment variables
    """
    try:
        base = Path(__file__).resolve().parent.parent
        env_path = Path(path) if path else (base / ".env")
        if not env_path.exists():
            # Also check CWD for dev usage
            alt = Path.cwd() / ".env"
            if alt.exists():
                env_path = alt
            else:
                return
        for raw in env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "#" in line:
                # allow trailing comments: KEY=VAL # comment
                line = line.split("#", 1)[0].strip()
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        # Intentionally swallow errors to avoid interfering with Django startup
        return

