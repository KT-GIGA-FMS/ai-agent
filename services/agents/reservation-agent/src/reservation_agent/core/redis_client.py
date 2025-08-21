import redis

from reservation_agent.core.config import settings

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def healthcheck() -> bool:
    try:
        get_client().ping()
        return True
    except Exception:
        return False
