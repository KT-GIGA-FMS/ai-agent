import redis

from reservation_agent.core.config import settings

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        redis_url = settings.REDIS_URL
        if not redis_url:
            raise ValueError("REDIS_URL is not set")

        # redis-py는 rediss:// 스킴이면 자동으로 TLS를 사용한다.
        # 일부 버전에서 ssl=True 전달 시 'unexpected keyword argument \"ssl\"' 오류가 발생하므로
        # 추가 kwargs 없이 URL만 사용한다. (필요 시 '?ssl_cert_reqs=none'을 URL에 포함)
        _client = redis.from_url(redis_url, decode_responses=True)
    return _client


def healthcheck() -> bool:
    try:
        get_client().ping()
        return True
    except Exception:
        return False
