import os
from pathlib import Path
from typing import Optional


def _clean(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip().strip('"').strip("'")
    if not cleaned or cleaned.startswith("#"):
        return None
    return cleaned


def get_secret(name: str, *, prefixes: tuple[str, ...] = ()) -> Optional[str]:
    env_value = _clean(os.getenv(name))
    if env_value and (not prefixes or env_value.startswith(prefixes)):
        return env_value

    env_path = Path(".env")
    if not env_path.exists():
        return env_value

    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(f"{name}="):
            continue
        raw_value = stripped.split("=", 1)[1].split(" #", 1)[0]
        value = _clean(raw_value)
        if value and (not prefixes or value.startswith(prefixes)):
            return value

    return env_value
