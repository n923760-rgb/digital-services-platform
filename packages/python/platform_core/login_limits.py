"""Atomic bounded login counters; normalized identities appear only as hashes."""

import hashlib

from redis.exceptions import RedisError

WINDOW_SECONDS = 900
SOURCE_LIMIT = 30
ACCOUNT_LIMIT = 10
PAIR_LIMIT = 5
COUNTERS = """
local counts = {}
for i,key in ipairs(KEYS) do
    counts[i] = redis.call('INCR',key)
    if redis.call('TTL',key) < 0 then
        redis.call('EXPIRE',key,ARGV[1])
    end
end
return counts
"""


def login_keys(source: str, username: str) -> tuple[str, str, str]:
    username = username.strip().lower()

    def key(scope, value):
        digest = hashlib.sha256(value.encode()).hexdigest()
        return f"admin:login:{{admin-login}}:{scope}:{digest}"

    return key("source", source), key("account", username), key("pair", source + "\0" + username)


async def login_allowed(
    redis, source: str, username: str, *, source_limit: int = SOURCE_LIMIT,
    account_limit: int = ACCOUNT_LIMIT, pair_limit: int = PAIR_LIMIT,
    window_seconds: int = WINDOW_SECONDS,
) -> bool:
    values = (source_limit, account_limit, pair_limit, window_seconds)
    if any(type(value) is not int or value < 1 for value in values):
        raise ValueError("invalid login limits")
    if redis is None:
        raise RedisError("login limiter unavailable")
    counts = await redis.eval(COUNTERS, 3, *login_keys(source, username), window_seconds)
    if (not isinstance(counts, (list, tuple)) or len(counts) != 3
            or any(type(count) is not int or count < 1 for count in counts)):
        raise RedisError("invalid login limiter response")
    return all(count <= limit for count, limit in zip(counts, values[:3], strict=True))
