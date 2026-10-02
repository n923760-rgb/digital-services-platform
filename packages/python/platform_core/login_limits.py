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


async def postgres_login_allowed(
    connection, source: str, username: str, *, source_limit: int = SOURCE_LIMIT,
    account_limit: int = ACCOUNT_LIMIT, pair_limit: int = PAIR_LIMIT,
    window_seconds: int = WINDOW_SECONDS,
) -> bool:
    """Same durable limits without a Redis runtime; all three counters commit atomically."""
    values = (source_limit, account_limit, pair_limit, window_seconds)
    if any(type(value) is not int or value < 1 for value in values):
        raise ValueError("invalid login limits")
    # Bounded housekeeping precedes the counter transaction and holds no counter locks.
    await connection.execute(
        """DELETE FROM admin_login_counters WHERE login_key IN (
           SELECT login_key FROM admin_login_counters WHERE expires_at<=now()
           ORDER BY expires_at,login_key LIMIT 100 FOR UPDATE SKIP LOCKED)""",
    )
    limits = dict(zip(login_keys(source, username), values[:3], strict=True))
    allowed = True
    async with connection.transaction():
        # Stable key ordering prevents deadlocks between overlapping accounts/sources.
        for key in sorted(limits):
            count = await connection.fetchval(
                """INSERT INTO admin_login_counters (login_key,attempts,expires_at)
                   VALUES ($1,1,now()+$2*interval '1 second')
                   ON CONFLICT (login_key) DO UPDATE SET
                   attempts=CASE WHEN admin_login_counters.expires_at<=now() THEN 1
                                 ELSE admin_login_counters.attempts+1 END,
                   expires_at=CASE WHEN admin_login_counters.expires_at<=now()
                                   THEN excluded.expires_at ELSE admin_login_counters.expires_at END
                   RETURNING attempts""", key, window_seconds,
            )
            allowed = allowed and count <= limits[key]
    return allowed
