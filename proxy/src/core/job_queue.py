from collections import OrderedDict
from typing import Any, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class JobQueue:
    """
    FIFO queue for mining jobs with size limit.

    Maintains a fixed number of recent jobs to handle late submissions
    while preventing memory growth.
    """

    def __init__(self, max_size: int = 10):
        """
        Initialize job queue.

        Args:
            max_size: Maximum number of jobs to keep (default: 10)
        """
        self.max_size = max_size
        self.jobs = OrderedDict()

    def add_job(self, job_id: str, job_data: dict[str, Any]) -> None:
        """
        Add a new job to the queue.

        If queue is at max capacity, removes oldest job (FIFO).

        Args:
            job_id: Unique job identifier
            job_data: Complete job data from mining.notify
        """
        if job_id in self.jobs:
            del self.jobs[job_id]

        self.jobs[job_id] = job_data

        while len(self.jobs) > self.max_size:
            oldest_id, _ = self.jobs.popitem(last=False)
            logger.debug(
                f"Evicted old job {oldest_id} from queue (max size: {self.max_size})"
            )

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve job data by ID.

        Args:
            job_id: Job identifier to lookup

        Returns:
            Job data if found, None otherwise
        """
        return self.jobs.get(job_id)

    def clear(self) -> None:
        """Clear all jobs from the queue."""
        self.jobs.clear()

    def __len__(self) -> int:
        """Return number of jobs in queue."""
        return len(self.jobs)

    def __contains__(self, job_id: str) -> bool:
        """Check if job exists in queue."""
        return job_id in self.jobs

    def get_all_job_ids(self) -> list[str]:
        """Get list of all job IDs in order (oldest to newest)."""
        return list(self.jobs.keys())

    def get_newest_job(self) -> Optional[tuple[str, dict[str, Any]]]:
        """
        Get the most recently added job.

        Returns:
            Tuple of (job_id, job_data) or None if queue is empty
        """
        if not self.jobs:
            return None
        job_id = next(reversed(self.jobs))
        return job_id, self.jobs[job_id]

    def get_oldest_job(self) -> Optional[tuple[str, dict[str, Any]]]:
        """
        Get the oldest job in queue.

        Returns:
            Tuple of (job_id, job_data) or None if queue is empty
        """
        if not self.jobs:
            return None
        job_id = next(iter(self.jobs))
        return job_id, self.jobs[job_id]
