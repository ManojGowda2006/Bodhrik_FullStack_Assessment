"""
Settings for pytest. Same as production settings, except:
- a throwaway secret key, so tests run without a .env,
- Redis database 15, so tests never touch dev data in database 0
  (each test flushes it),
- a fast password hasher (hashing is deliberately slow in production).
Postgres is real; pytest-django creates and drops a separate test_ database.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-secret")

from config.settings import *  # noqa: E402, F403
from config.settings import REDIS_URL  # noqa: E402

TEST_REDIS_URL = REDIS_URL.rsplit("/", 1)[0] + "/15"

CACHES["default"]["LOCATION"] = TEST_REDIS_URL  # noqa: F405
RQ_QUEUES["default"]["URL"] = TEST_REDIS_URL  # noqa: F405

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
