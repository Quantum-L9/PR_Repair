from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values


def load_dotenv_local(path: str = ".env.local") -> dict[str, str]:
    """
    Load key/value pairs from a local dotenv file without logging secrets.

    The function is intentionally side-effect free:
    - it does not mutate os.environ
    - it returns only keys with non-null values
    - it treats a missing file as an empty mapping
    """
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return {}

    raw_values = dotenv_values(dotenv_path)
    loaded: dict[str, str] = {}
    for key, value in raw_values.items():
        if key and value not in (None, ""):
            loaded[key] = value
    return loaded
