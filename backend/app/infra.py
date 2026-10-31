"""Cross-cutting infrastructure: rate limiting (Redis or in-memory) and WebSocket broadcasting."""
import asyncio
import json
import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, WebSocket

from .config import get_settings

log = logging.getLogger("sentinel")


# ---------------------------------------------------------------- rate limiting
class RateLimiter:
    """Fixed-window limiter. Uses Redis when REDIS_URL is configured (multi-instance safe),
    otherwise a per-process sliding window."""

    def __init__(self) -> None:
        self._redis = None
        self._local: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
        url = get_settings().redis_url
        if url:
            try:
                import redis

                self._redis = redis.Redis.from_url(url, socket_timeout=0.5)
                self._redis.ping()
                log.info("Rate limiter using Redis")
            except Exception as exc:  # degrade gracefully, never block payments on Redis
                log.warning("Redis unavailable (%s); using in-memory rate limiting", exc)
                self._redis = None

    @property
    def backend(self) -> str:
        return "redis" if self._redis else "memory"

    def hit(self, key: str, limit: int, window: int = 60) -> bool:
        if self._redis:
            try:
                bucket = f"rl:{key}:{int(time.time() // window)}"
                n = self._redis.incr(bucket)
                if n == 1:
                    self._redis.expire(bucket, window)
                return n <= limit
            except Exception:
                pass
        now = time.monotonic()
        with self._lock:
            q = self._local[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


limiter = RateLimiter()


def rate_limit(limit: int | None = None, scope: str = "api"):
    def _dep(request: Request) -> None:
        n = limit or get_settings().rate_limit_per_minute
        ident = request.client.host if request.client else "unknown"
        if not limiter.hit(f"{scope}:{ident}", n):
            raise HTTPException(429, "Rate limit exceeded. Slow down.")

    return _dep


# ---------------------------------------------------------------- websockets
class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def _send_all(self, message: str) -> None:
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws)

    def broadcast(self, event: str, data: dict) -> None:
        """Thread-safe: callable from sync endpoints and background workers."""
        if not self.loop or not self.active:
            return
        msg = json.dumps({"event": event, "data": data, "ts": time.time()}, default=str)
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            self.loop.create_task(self._send_all(msg))
        else:
            asyncio.run_coroutine_threadsafe(self._send_all(msg), self.loop)


ws_manager = ConnectionManager()
