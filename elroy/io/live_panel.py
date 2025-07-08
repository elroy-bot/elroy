import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Set

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class JobStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"


@dataclass
class BackgroundJob:
    id: str
    name: str
    status: JobStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    progress: Optional[str] = None
    error: Optional[str] = None


class LivePanelManager:
    def __init__(self, console: Console):
        self.console = console
        self.jobs: Dict[str, BackgroundJob] = {}
        self.live: Optional[Live] = None
        self.lock = threading.Lock()
        self.active_jobs: Set[str] = set()

    def _create_status_table(self) -> Table:
        """Create a table showing current background operations."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Job", style="cyan", width=20)
        table.add_column("Status", width=12)
        table.add_column("Progress", width=30)
        table.add_column("Duration", width=10)

        with self.lock:
            for job in self.jobs.values():
                # Status styling
                if job.status == JobStatus.RUNNING:
                    status_text = Text("🔄 Running", style="yellow")
                elif job.status == JobStatus.COMPLETED:
                    status_text = Text("✅ Done", style="green")
                elif job.status == JobStatus.FAILED:
                    status_text = Text("❌ Failed", style="red")
                elif job.status == JobStatus.SCHEDULED:
                    status_text = Text("⏳ Scheduled", style="blue")
                else:
                    status_text = Text(job.status.value, style="white")

                # Progress text
                progress_text = job.progress or ""
                if job.error:
                    progress_text = f"Error: {job.error}"

                # Duration calculation
                duration = ""
                if job.start_time:
                    end_time = job.end_time or datetime.now()
                    delta = end_time - job.start_time
                    duration = f"{delta.total_seconds():.1f}s"

                table.add_row(job.name, status_text, progress_text, duration)

        return table

    def _create_panel(self) -> Panel:
        """Create the live panel with background job status."""
        table = self._create_status_table()

        if not self.jobs:
            return Panel(Text("No background operations", style="dim"), title="Background Operations", expand=False, border_style="blue")

        return Panel(table, title="Background Operations", expand=False, border_style="blue")

    @contextmanager
    def live_panel(self):
        """Context manager for the live panel display."""
        try:
            self.live = Live(self._create_panel(), console=self.console, refresh_per_second=2, auto_refresh=True)
            self.live.start()
            yield self
        finally:
            if self.live:
                self.live.stop()
                self.live = None

    def add_job(self, job_id: str, name: str, status: JobStatus = JobStatus.SCHEDULED) -> None:
        """Add a new background job to track."""
        with self.lock:
            self.jobs[job_id] = BackgroundJob(
                id=job_id, name=name, status=status, start_time=datetime.now() if status == JobStatus.RUNNING else None
            )
            if status == JobStatus.RUNNING:
                self.active_jobs.add(job_id)
            self._update_live_display()

    def update_job(self, job_id: str, **kwargs) -> None:
        """Update a background job's status, progress, etc."""
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]

                # Update fields
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)

                # Handle status transitions
                if "status" in kwargs:
                    new_status = kwargs["status"]
                    if new_status == JobStatus.RUNNING and job.start_time is None:
                        job.start_time = datetime.now()
                        self.active_jobs.add(job_id)
                    elif new_status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                        job.end_time = datetime.now()
                        self.active_jobs.discard(job_id)

                self._update_live_display()

    def remove_job(self, job_id: str) -> None:
        """Remove a job from tracking."""
        with self.lock:
            if job_id in self.jobs:
                del self.jobs[job_id]
                self.active_jobs.discard(job_id)
                self._update_live_display()

    def complete_job(self, job_id: str, progress: Optional[str] = None) -> None:
        """Mark a job as completed."""
        updates = {"status": JobStatus.COMPLETED}
        if progress:
            updates["progress"] = progress
        self.update_job(job_id, **updates)

    def fail_job(self, job_id: str, error: str) -> None:
        """Mark a job as failed with error message."""
        self.update_job(job_id, status=JobStatus.FAILED, error=error)

    def _update_live_display(self) -> None:
        """Update the live display if active."""
        if self.live:
            self.live.update(self._create_panel())

    @property
    def has_active_jobs(self) -> bool:
        """Check if there are any active background jobs."""
        with self.lock:
            return bool(self.active_jobs)

    def clear_completed_jobs(self) -> None:
        """Remove all completed and failed jobs."""
        with self.lock:
            to_remove = [job_id for job_id, job in self.jobs.items() if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]]
            for job_id in to_remove:
                del self.jobs[job_id]
            self._update_live_display()
