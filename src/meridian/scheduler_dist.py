import random
import time
import structlog
from typing import Callable, Any
from redis import Redis
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = structlog.get_logger()


class DistributedScheduler:
    def __init__(self, redis_client: Redis[Any]) -> None:
        self.scheduler = BackgroundScheduler()
        self.redis = redis_client
        self.scheduler.start()

    def schedule_job(
        self, func: Callable[[], None], interval_seconds: int, job_id: str
    ) -> None:
        """
        Schedules a job that attempts to acquire a distributed lock before running.
        """
        if self.scheduler.get_job(job_id):
            logger.info("Job already exists, skipping", job_id=job_id)
            return

        # Wrapper to handle locking
        def locked_job() -> None:
            # Randomized jitter to prevent thundering herd
            time.sleep(random.uniform(0, 1.0))  # nosec

            lock_key = f"lock:{job_id}"
            # Lock TTL should be slightly less than interval to allow next run
            lock_ttl = max(1, int(interval_seconds * 0.9))

            # Try to acquire lock (SETNX)
            acquired = self.redis.set(lock_key, "locked", ex=lock_ttl, nx=True)

            if acquired:
                logger.info("Lock acquired, running job", job_id=job_id)
                try:
                    func()
                except Exception as e:
                    logger.error("Job failed", job_id=job_id, error=str(e))
                # We do NOT release the lock early. We rely on TTL.
                # This enforces the interval across the cluster.
            else:
                logger.debug("Lock not acquired, skipping", job_id=job_id)

        self.scheduler.add_job(
            locked_job,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=job_id,
            replace_existing=True,
        )
        logger.info(
            "Scheduled distributed job", job_id=job_id, interval=interval_seconds
        )

    def shutdown(self) -> None:
        self.scheduler.shutdown()
