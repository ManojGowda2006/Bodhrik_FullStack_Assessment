"""
Redis cache for the slot list (GET /api/slots/), the hottest read path:
every customer browsing for a time hits it.

Pattern: cache-aside with a version number.
- Read:  build a key from the current version + query params, try Redis,
         on a miss query Postgres and store the result for SLOT_LIST_TTL.
- Write: any change to a slot or booking bumps the version. Every old key
         is then never read again and expires on its own via its TTL.

A version key means one write invalidates every cached page and filter
combination, without scanning Redis for matching keys (KEYS is O(n) and
blocks Redis).

The slot list is the same for every user, so one shared cache entry is safe.
Per-user data such as bookings is deliberately not cached this way.

If Redis is down, reads fall back to Postgres: the cache must never be the
reason a request fails.
"""

import logging
import time
from urllib.parse import urlencode

from django.core.cache import cache

logger = logging.getLogger(__name__)

SLOT_LIST_TTL = 60  # seconds; the safety net if an invalidation is ever missed
VERSION_KEY = "slots:list:version"


def slot_list_key(query_params):
    version = cache.get_or_set(VERSION_KEY, time.time_ns(), timeout=None)
    params = urlencode(sorted(query_params.items()))
    return f"slots:list:v{version}:{params}"


def get_slot_list(query_params):
    """Returns (key, cached data or None). key is None if Redis is unavailable."""
    try:
        key = slot_list_key(query_params)
        return key, cache.get(key)
    except Exception:
        logger.warning("Slot list cache unavailable, reading from DB", exc_info=True)
        return None, None


def set_slot_list(key, data):
    if key is None:
        return
    try:
        cache.set(key, data, SLOT_LIST_TTL)
    except Exception:
        logger.warning("Could not write slot list cache", exc_info=True)


def invalidate_slot_lists():
    # A new unique version (not INCR) so this also works if the key was evicted.
    try:
        cache.set(VERSION_KEY, time.time_ns(), timeout=None)
    except Exception:
        logger.warning("Could not invalidate slot list cache", exc_info=True)
