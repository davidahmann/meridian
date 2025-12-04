from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Callable
import structlog

logger = structlog.get_logger()


class Scheduler:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    def schedule_job(
        self, func: Callable[[], None], interval_seconds: int, job_id: str
    ) -> None:
        """
        Schedules a function to run at a fixed interval.
        """
        if self.scheduler.get_job(job_id):
            logger.info("Job already exists, skipping", job_id=job_id)
            return

        self.scheduler.add_job(
            func,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=job_id,
            replace_existing=True,
        )
        logger.info("Scheduled job", job_id=job_id, interval=interval_seconds)

    def shutdown(self) -> None:
        self.scheduler.shutdown()
