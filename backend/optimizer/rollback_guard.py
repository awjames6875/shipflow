"""
Rollback Guard - Safety Monitoring System

Monitors workflow health and automatically rolls back to baseline config when:
- Success rate drops below threshold (70%)
- Quality score drops significantly (15% from baseline)
- Consecutive failures exceed limit (3)

This ensures the system stays stable even with fully autonomous improvements.
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple

from .database import Database
from .config_store import ConfigStore
from .experiments import ExperimentManager

logger = logging.getLogger(__name__)


class RollbackGuard:
    """Monitors for regressions and triggers rollbacks."""

    # Thresholds for triggering rollback
    SUCCESS_RATE_THRESHOLD = 0.70  # Below 70% = rollback
    QUALITY_DROP_THRESHOLD = 0.15  # 15% quality drop = rollback
    CONSECUTIVE_FAILURES_LIMIT = 3  # N failures in a row = rollback

    # Cooldown after rollback (prevent thrashing)
    ROLLBACK_COOLDOWN_HOURS = 24

    def __init__(
        self,
        db: Database,
        config_store: ConfigStore,
        experiment_manager: ExperimentManager
    ):
        self.db = db
        self.config_store = config_store
        self.experiment_manager = experiment_manager

    def check_health(self) -> dict:
        """Check current system health against thresholds.

        Returns:
            Dict with health metrics and status
        """
        health = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "issues": [],
            "metrics": {}
        }

        # Get recent runs (last 24 hours)
        rows = self.db.execute(
            """
            SELECT
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                AVG(script_quality_score) as avg_quality
            FROM workflow_runs
            WHERE started_at >= datetime('now', '-24 hours')
            """
        )

        if not rows or not rows[0]["total_runs"]:
            health["metrics"]["total_runs"] = 0
            health["status"] = "no_data"
            return health

        row = rows[0]
        total = row["total_runs"] or 0
        successful = row["successful"] or 0
        failed = row["failed"] or 0
        avg_quality = row["avg_quality"]

        health["metrics"]["total_runs"] = total
        health["metrics"]["successful"] = successful
        health["metrics"]["failed"] = failed
        health["metrics"]["success_rate"] = successful / total if total > 0 else 0
        health["metrics"]["avg_quality"] = avg_quality

        # Check success rate
        if health["metrics"]["success_rate"] < self.SUCCESS_RATE_THRESHOLD:
            health["status"] = "critical"
            health["issues"].append(
                f"Success rate {health['metrics']['success_rate']:.1%} below threshold {self.SUCCESS_RATE_THRESHOLD:.0%}"
            )

        # Check consecutive failures
        consecutive = self._get_consecutive_failures()
        health["metrics"]["consecutive_failures"] = consecutive
        if consecutive >= self.CONSECUTIVE_FAILURES_LIMIT:
            health["status"] = "critical"
            health["issues"].append(
                f"Consecutive failures: {consecutive} (limit: {self.CONSECUTIVE_FAILURES_LIMIT})"
            )

        # Check quality drop from baseline
        baseline_quality = self._get_baseline_quality()
        if baseline_quality and avg_quality:
            quality_drop = (baseline_quality - avg_quality) / baseline_quality
            health["metrics"]["baseline_quality"] = baseline_quality
            health["metrics"]["quality_drop"] = quality_drop

            if quality_drop > self.QUALITY_DROP_THRESHOLD:
                health["status"] = "critical"
                health["issues"].append(
                    f"Quality dropped {quality_drop:.1%} from baseline (threshold: {self.QUALITY_DROP_THRESHOLD:.0%})"
                )

        # If any issues but not critical, mark as degraded
        if health["issues"] and health["status"] != "critical":
            health["status"] = "degraded"

        return health

    def _get_consecutive_failures(self) -> int:
        """Get count of consecutive recent failures."""
        rows = self.db.execute(
            """
            SELECT status FROM workflow_runs
            ORDER BY started_at DESC
            LIMIT 10
            """
        )

        consecutive = 0
        for row in rows:
            if row["status"] == "failed":
                consecutive += 1
            else:
                break  # Stop at first success

        return consecutive

    def _get_baseline_quality(self) -> float | None:
        """Get average quality score from baseline period (first week of runs)."""
        rows = self.db.execute(
            """
            SELECT AVG(script_quality_score) as avg_quality
            FROM workflow_runs
            WHERE config_version_id = (
                SELECT id FROM config_versions WHERE is_baseline = 1 LIMIT 1
            )
            AND script_quality_score IS NOT NULL
            """
        )

        if rows and rows[0]["avg_quality"]:
            return rows[0]["avg_quality"]

        # Fallback: use first 10 runs as baseline
        rows = self.db.execute(
            """
            SELECT AVG(script_quality_score) as avg_quality
            FROM (
                SELECT script_quality_score FROM workflow_runs
                WHERE script_quality_score IS NOT NULL
                ORDER BY started_at ASC
                LIMIT 10
            )
            """
        )

        return rows[0]["avg_quality"] if rows else None

    def should_rollback(self) -> Tuple[bool, str]:
        """Determine if rollback is needed.

        Returns:
            (should_rollback, reason)
        """
        # Check cooldown
        if self._is_in_cooldown():
            return False, "In rollback cooldown period"

        health = self.check_health()

        if health["status"] == "critical":
            return True, "; ".join(health["issues"])

        return False, "Healthy"

    def _is_in_cooldown(self) -> bool:
        """Check if we're in post-rollback cooldown."""
        rows = self.db.execute(
            """
            SELECT timestamp FROM change_log
            WHERE action = 'rollback'
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )

        if not rows:
            return False

        last_rollback = rows[0]["timestamp"]
        if isinstance(last_rollback, str):
            last_rollback = datetime.fromisoformat(last_rollback)

        cooldown_end = last_rollback + timedelta(hours=self.ROLLBACK_COOLDOWN_HOURS)
        return datetime.now() < cooldown_end

    def execute_rollback(self, reason: str) -> int:
        """Execute rollback to baseline configuration.

        Args:
            reason: Why the rollback was triggered

        Returns:
            The baseline config version ID
        """
        logger.warning(f"Executing rollback: {reason}")

        # Abandon any running experiments
        running_experiments = self.experiment_manager.get_running_experiments()
        for exp in running_experiments:
            self.experiment_manager.abandon_experiment(
                exp.id,
                f"Abandoned due to rollback: {reason}"
            )

        # Rollback to baseline
        baseline_id = self.config_store.rollback_to_baseline()

        # Log the rollback
        self.db.execute(
            """
            INSERT INTO change_log (action, details, config_version_id, triggered_by)
            VALUES (?, ?, ?, ?)
            """,
            ("rollback", reason, baseline_id, "rollback_guard")
        )

        logger.warning(f"Rolled back to baseline config {baseline_id}")
        return baseline_id

    def pre_run_check(self) -> Tuple[bool, str]:
        """Check if we should run the workflow or rollback first.

        Call this before each workflow run.

        Returns:
            (ok_to_run, message)
        """
        should_rollback, reason = self.should_rollback()

        if should_rollback:
            self.execute_rollback(reason)
            return True, f"Rolled back before run: {reason}"

        return True, "OK"

    def get_rollback_history(self, limit: int = 10) -> list:
        """Get recent rollback events."""
        rows = self.db.execute(
            """
            SELECT * FROM change_log
            WHERE action = 'rollback'
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in rows]

    def get_health_summary(self) -> dict:
        """Get a summary of system health over time."""
        # Last 7 days, daily buckets
        rows = self.db.execute(
            """
            SELECT
                date(started_at) as date,
                COUNT(*) as runs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
                AVG(script_quality_score) as avg_quality,
                AVG(total_duration_ms) as avg_duration
            FROM workflow_runs
            WHERE started_at >= datetime('now', '-7 days')
            GROUP BY date(started_at)
            ORDER BY date DESC
            """
        )

        return {
            "current": self.check_health(),
            "daily_history": [dict(row) for row in rows]
        }
