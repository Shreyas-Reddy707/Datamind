"""DataMind v2 Taskiq Broker Configuration.

Configures asynchronous task broker:
Uses InMemoryBroker for test/development environments and ListQueueBroker with Redis
for production workloads.
"""

from __future__ import annotations

import logging

from taskiq import InMemoryBroker

from app.config import settings

logger = logging.getLogger("datamind.workers.broker")

if settings.ENVIRONMENT in ("test", "development"):
    # In-process asynchronous broker for test isolation and rapid execution
    broker = InMemoryBroker()
else:
    try:
        from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

        result_backend = RedisAsyncResultBackend(redis_url=settings.REDIS_URL)
        broker = ListQueueBroker(
            url=settings.REDIS_URL,
        ).with_result_backend(result_backend)
    except Exception as e:
        logger.warning("Failed to initialize Redis Taskiq broker (%s), falling back to InMemoryBroker", e)
        broker = InMemoryBroker()
