import os


def limiter_storage_options() -> dict[str, str]:
    redis_url = os.getenv("REDIS_URL")
    return {"storage_uri": redis_url} if redis_url else {}
