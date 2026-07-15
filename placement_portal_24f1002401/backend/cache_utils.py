import json

from config import CACHE_TTL_SECONDS, REDIS_URL

_redis_client = None
_memory_cache = {}


def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis

        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception:
        _redis_client = False
        return None


def cache_get(key):
    client = get_redis()
    if client:
        try:
            raw = client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None
    item = _memory_cache.get(key)
    if not item:
        return None
    import time

    value, expires_at = item
    if time.time() > expires_at:
        _memory_cache.pop(key, None)
        return None
    return value


def cache_set(key, value, ttl=None):
    ttl = CACHE_TTL_SECONDS if ttl is None else ttl
    client = get_redis()
    if client:
        try:
            client.setex(key, ttl, json.dumps(value))
            return True
        except Exception:
            pass
    import time

    _memory_cache[key] = (value, time.time() + ttl)
    return True


def cache_delete_prefix(prefix):
    client = get_redis()
    if client:
        try:
            for key in client.scan_iter(match=f"{prefix}*"):
                client.delete(key)
        except Exception:
            pass
    for key in list(_memory_cache.keys()):
        if key.startswith(prefix):
            _memory_cache.pop(key, None)


def cache_delete(key):
    client = get_redis()
    if client:
        try:
            client.delete(key)
        except Exception:
            pass
    _memory_cache.pop(key, None)
