"""
Metrics Collector for Self-Improving Workflow

Wraps each workflow step to capture:
- Timing (duration in milliseconds)
- Success/failure status
- Error messages
- Quality signals (script quality score)
"""

import time
import uuid
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from contextlib import contextmanager

from .database import Database

logger = logging.getLogger(__name__)


@dataclass
class StepMetrics:
    """Metrics for a single workflow step."""
    step_name: str
    started_at: datetime
    duration_ms: int = 0
    success: bool = False
    error_message: Optional[str] = None


@dataclass
class RunMetrics:
    """Aggregated metrics for a complete workflow run."""
    run_id: str
    started_at: datetime
    config_version_id: Optional[int] = None
    industry: Optional[str] = None
    experiment_id: Optional[int] = None
    experiment_variant: Optional[str] = None

    # Step metrics
    steps: dict = field(default_factory=dict)

    # Quality metrics
    script_quality_score: Optional[float] = None
    video_generated: bool = False
    platforms_posted: int = 0
    platforms_failed: int = 0

    # Final status
    status: str = "running"
    error_step: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None


class MetricsCollector:
    """Collects and stores metrics from workflow runs."""

    def __init__(self, db: Database):
        self.db = db
        self.current_run: Optional[RunMetrics] = None

    def start_run(
        self,
        industry: str,
        config_version_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
        experiment_variant: Optional[str] = None
    ) -> str:
        """Begin tracking a new workflow run. Returns run_id."""
        run_id = str(uuid.uuid4())
        started_at = datetime.now()

        self.current_run = RunMetrics(
            run_id=run_id,
            started_at=started_at,
            config_version_id=config_version_id,
            industry=industry,
            experiment_id=experiment_id,
            experiment_variant=experiment_variant
        )

        # Insert initial record
        self.db.execute_insert(
            """
            INSERT INTO workflow_runs
            (run_id, started_at, status, config_version_id, industry, experiment_id, experiment_variant)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, started_at.isoformat(), "running", config_version_id,
             industry, experiment_id, experiment_variant)
        )

        logger.info(f"Started workflow run: {run_id}")
        return run_id

    @contextmanager
    def track_step(self, step_name: str):
        """Context manager to track a single workflow step."""
        if not self.current_run:
            raise RuntimeError("No active run. Call start_run() first.")

        step = StepMetrics(step_name=step_name, started_at=datetime.now())
        start_time = time.time()

        try:
            yield step
            step.success = True
        except Exception as e:
            step.success = False
            step.error_message = str(e)
            self.current_run.error_step = step_name
            self.current_run.error_message = str(e)
            raise
        finally:
            step.duration_ms = int((time.time() - start_time) * 1000)
            self.current_run.steps[step_name] = step
            logger.info(f"Step '{step_name}': {'OK' if step.success else 'FAILED'} ({step.duration_ms}ms)")

    def record_quality_score(self, score: float):
        """Record the LLM-evaluated quality score (0-1)."""
        if not self.current_run:
            raise RuntimeError("No active run. Call start_run() first.")
        self.current_run.script_quality_score = max(0.0, min(1.0, score))
        logger.info(f"Quality score: {self.current_run.script_quality_score:.2f}")

    def record_video_generated(self, success: bool = True):
        """Record that a video was successfully generated."""
        if not self.current_run:
            raise RuntimeError("No active run. Call start_run() first.")
        self.current_run.video_generated = success

    def record_platform_result(self, success: bool):
        """Record a platform posting result."""
        if not self.current_run:
            raise RuntimeError("No active run. Call start_run() first.")
        if success:
            self.current_run.platforms_posted += 1
        else:
            self.current_run.platforms_failed += 1

    def complete_run(self, status: str = "completed"):
        """Finalize the run and save all metrics to database."""
        if not self.current_run:
            raise RuntimeError("No active run. Call start_run() first.")

        self.current_run.status = status
        self.current_run.completed_at = datetime.now()

        # Calculate total duration
        total_duration_ms = int(
            (self.current_run.completed_at - self.current_run.started_at).total_seconds() * 1000
        )

        # Extract step durations
        research_ms = self.current_run.steps.get("research", StepMetrics("", datetime.now())).duration_ms
        research_ms += self.current_run.steps.get("research_deep", StepMetrics("", datetime.now())).duration_ms
        script_ms = self.current_run.steps.get("write_script", StepMetrics("", datetime.now())).duration_ms
        video_ms = self.current_run.steps.get("create_video", StepMetrics("", datetime.now())).duration_ms
        video_ms += self.current_run.steps.get("wait_for_video", StepMetrics("", datetime.now())).duration_ms
        posting_ms = self.current_run.steps.get("post_to_platforms", StepMetrics("", datetime.now())).duration_ms

        # Update database
        self.db.execute(
            """
            UPDATE workflow_runs SET
                completed_at = ?,
                status = ?,
                script_quality_score = ?,
                video_generated = ?,
                platforms_posted = ?,
                platforms_failed = ?,
                total_duration_ms = ?,
                research_duration_ms = ?,
                script_duration_ms = ?,
                video_duration_ms = ?,
                posting_duration_ms = ?,
                error_step = ?,
                error_message = ?
            WHERE run_id = ?
            """,
            (
                self.current_run.completed_at.isoformat(),
                status,
                self.current_run.script_quality_score,
                1 if self.current_run.video_generated else 0,
                self.current_run.platforms_posted,
                self.current_run.platforms_failed,
                total_duration_ms,
                research_ms,
                script_ms,
                video_ms,
                posting_ms,
                self.current_run.error_step,
                self.current_run.error_message,
                self.current_run.run_id
            )
        )

        logger.info(f"Completed run {self.current_run.run_id}: {status} ({total_duration_ms}ms)")

        run_id = self.current_run.run_id
        self.current_run = None
        return run_id

    def get_recent_runs(self, hours: int = 24, limit: int = 100) -> list:
        """Get recent workflow runs for analysis."""
        rows = self.db.execute(
            """
            SELECT * FROM workflow_runs
            WHERE started_at >= datetime('now', ?)
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (f"-{hours} hours", limit)
        )
        return [dict(row) for row in rows]

    def get_aggregated_metrics(self, days: int = 7) -> dict:
        """Get aggregated metrics for the past N days."""
        rows = self.db.execute(
            """
            SELECT
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
                AVG(script_quality_score) as avg_quality,
                AVG(total_duration_ms) as avg_duration_ms,
                AVG(research_duration_ms) as avg_research_ms,
                AVG(script_duration_ms) as avg_script_ms,
                AVG(video_duration_ms) as avg_video_ms,
                AVG(posting_duration_ms) as avg_posting_ms,
                SUM(platforms_posted) as total_platforms_posted,
                SUM(platforms_failed) as total_platforms_failed
            FROM workflow_runs
            WHERE started_at >= datetime('now', ?)
            """,
            (f"-{days} days",)
        )

        row = rows[0] if rows else None
        if not row:
            return {}

        result = dict(row)

        # Calculate success rate
        total = result.get("total_runs", 0) or 0
        successful = result.get("successful_runs", 0) or 0
        result["success_rate"] = successful / total if total > 0 else 0.0

        return result

    def get_run_by_id(self, run_id: str) -> Optional[dict]:
        """Get a specific run by ID."""
        rows = self.db.execute(
            "SELECT * FROM workflow_runs WHERE run_id = ?",
            (run_id,)
        )
        return dict(rows[0]) if rows else None
