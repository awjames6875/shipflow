"""
Experiment Manager for A/B Testing

Manages controlled experiments to test configuration changes:
- Creates experiments with control and variant configs
- Randomly assigns runs to control or variant
- Tracks results and calculates statistical significance
- Auto-concludes experiments when significance is reached
"""

import random
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from math import sqrt

from .database import Database
from .config_store import ConfigStore

logger = logging.getLogger(__name__)


@dataclass
class Experiment:
    """An A/B experiment."""
    id: int
    name: str
    hypothesis: str
    status: str
    control_config_id: int
    variant_config_id: int
    control_runs: int = 0
    variant_runs: int = 0
    control_success_rate: Optional[float] = None
    variant_success_rate: Optional[float] = None
    control_avg_quality: Optional[float] = None
    variant_avg_quality: Optional[float] = None
    control_avg_duration_ms: Optional[int] = None
    variant_avg_duration_ms: Optional[int] = None
    winner: Optional[str] = None
    statistical_significance: Optional[float] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class ExperimentManager:
    """Manages A/B experiments for workflow optimization."""

    MIN_RUNS_FOR_SIGNIFICANCE = 10  # Per variant
    SIGNIFICANCE_THRESHOLD = 0.05  # p-value threshold
    MAX_CONCURRENT_EXPERIMENTS = 1

    def __init__(self, db: Database, config_store: ConfigStore):
        self.db = db
        self.config_store = config_store

    def _row_to_experiment(self, row) -> Experiment:
        """Convert database row to Experiment."""
        return Experiment(
            id=row["id"],
            name=row["name"],
            hypothesis=row["hypothesis"] or "",
            status=row["status"],
            control_config_id=row["control_config_id"],
            variant_config_id=row["variant_config_id"],
            control_runs=row["control_runs"] or 0,
            variant_runs=row["variant_runs"] or 0,
            control_success_rate=row["control_success_rate"],
            variant_success_rate=row["variant_success_rate"],
            control_avg_quality=row["control_avg_quality"],
            variant_avg_quality=row["variant_avg_quality"],
            control_avg_duration_ms=row["control_avg_duration_ms"],
            variant_avg_duration_ms=row["variant_avg_duration_ms"],
            winner=row["winner"],
            statistical_significance=row["statistical_significance"],
            started_at=row["started_at"],
            ended_at=row["ended_at"]
        )

    def get_running_experiments(self) -> list[Experiment]:
        """Get all currently running experiments."""
        rows = self.db.execute(
            "SELECT * FROM experiments WHERE status = 'running' ORDER BY started_at DESC"
        )
        return [self._row_to_experiment(row) for row in rows]

    def get_experiment_by_id(self, experiment_id: int) -> Optional[Experiment]:
        """Get an experiment by ID."""
        rows = self.db.execute(
            "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
        )
        if rows:
            return self._row_to_experiment(rows[0])
        return None

    def can_create_experiment(self) -> bool:
        """Check if we can create a new experiment."""
        running = self.get_running_experiments()
        return len(running) < self.MAX_CONCURRENT_EXPERIMENTS

    def create_experiment(
        self,
        name: str,
        hypothesis: str,
        variant_changes: dict
    ) -> Experiment:
        """Create a new A/B experiment with a variant config.

        Args:
            name: Short descriptive name for the experiment
            hypothesis: What we expect to improve and why
            variant_changes: Dict of config changes to test

        Returns:
            The created Experiment
        """
        if not self.can_create_experiment():
            raise RuntimeError(
                f"Cannot create experiment: max {self.MAX_CONCURRENT_EXPERIMENTS} concurrent experiments"
            )

        # Get current active config as control
        control = self.config_store.get_active_config()
        if not control.id:
            raise RuntimeError("No active config found for control")

        # Create variant config
        variant_id = self.config_store.create_version(
            changes=variant_changes,
            source="experiment",
            reason=f"Experiment variant: {name}"
        )

        # Create experiment record
        experiment_id = self.db.execute_insert(
            """
            INSERT INTO experiments (name, hypothesis, control_config_id, variant_config_id, status)
            VALUES (?, ?, ?, ?, 'running')
            """,
            (name, hypothesis, control.id, variant_id)
        )

        logger.info(f"Created experiment {experiment_id}: {name}")
        logger.info(f"  Control: config {control.id}")
        logger.info(f"  Variant: config {variant_id}")

        return self.get_experiment_by_id(experiment_id)

    def get_config_for_run(self) -> Tuple[int, Optional[int], Optional[str]]:
        """Get config ID for the next run.

        Returns:
            Tuple of (config_id, experiment_id, variant_type)
            - config_id: Which config to use
            - experiment_id: If part of experiment, the experiment ID (else None)
            - variant_type: 'control' or 'variant' (else None)
        """
        running = self.get_running_experiments()

        if not running:
            # No experiments, use active config
            config = self.config_store.get_active_config()
            return (config.id, None, None)

        # Pick the first running experiment
        exp = running[0]

        # 50/50 random assignment
        if random.random() < 0.5:
            return (exp.control_config_id, exp.id, "control")
        else:
            return (exp.variant_config_id, exp.id, "variant")

    def record_run_result(
        self,
        experiment_id: int,
        variant: str,
        success: bool,
        quality_score: Optional[float],
        duration_ms: int
    ) -> None:
        """Record results from a workflow run.

        Args:
            experiment_id: The experiment this run was part of
            variant: 'control' or 'variant'
            success: Whether the run completed successfully
            quality_score: Quality score (0-1) if available
            duration_ms: Total duration in milliseconds
        """
        exp = self.get_experiment_by_id(experiment_id)
        if not exp:
            logger.error(f"Experiment {experiment_id} not found")
            return

        if exp.status != "running":
            logger.warning(f"Experiment {experiment_id} is not running, ignoring result")
            return

        # Update counts and recalculate metrics
        if variant == "control":
            self._update_variant_metrics(
                experiment_id, "control", exp.control_config_id,
                success, quality_score, duration_ms
            )
        else:
            self._update_variant_metrics(
                experiment_id, "variant", exp.variant_config_id,
                success, quality_score, duration_ms
            )

        # Check if we should conclude the experiment
        self._check_and_conclude(experiment_id)

    def _update_variant_metrics(
        self,
        experiment_id: int,
        variant: str,
        config_id: int,
        success: bool,
        quality_score: Optional[float],
        duration_ms: int
    ):
        """Update metrics for a variant."""
        # Get all runs for this variant
        runs = self.db.execute(
            """
            SELECT status, script_quality_score, total_duration_ms
            FROM workflow_runs
            WHERE experiment_id = ? AND experiment_variant = ?
            """,
            (experiment_id, variant)
        )

        # Add current result (not yet in DB, will be added by metrics collector)
        runs_list = [dict(r) for r in runs]
        runs_list.append({
            "status": "completed" if success else "failed",
            "script_quality_score": quality_score,
            "total_duration_ms": duration_ms
        })

        # Calculate metrics
        total = len(runs_list)
        successful = sum(1 for r in runs_list if r["status"] == "completed")
        success_rate = successful / total if total > 0 else 0

        qualities = [r["script_quality_score"] for r in runs_list if r["script_quality_score"] is not None]
        avg_quality = sum(qualities) / len(qualities) if qualities else None

        durations = [r["total_duration_ms"] for r in runs_list if r["total_duration_ms"] is not None]
        avg_duration = int(sum(durations) / len(durations)) if durations else None

        # Update experiment
        if variant == "control":
            self.db.execute(
                """
                UPDATE experiments SET
                    control_runs = ?,
                    control_success_rate = ?,
                    control_avg_quality = ?,
                    control_avg_duration_ms = ?
                WHERE id = ?
                """,
                (total, success_rate, avg_quality, avg_duration, experiment_id)
            )
        else:
            self.db.execute(
                """
                UPDATE experiments SET
                    variant_runs = ?,
                    variant_success_rate = ?,
                    variant_avg_quality = ?,
                    variant_avg_duration_ms = ?
                WHERE id = ?
                """,
                (total, success_rate, avg_quality, avg_duration, experiment_id)
            )

    def _check_and_conclude(self, experiment_id: int):
        """Check if experiment has reached significance and conclude if so."""
        exp = self.get_experiment_by_id(experiment_id)
        if not exp:
            return

        # Need minimum runs for both variants
        if exp.control_runs < self.MIN_RUNS_FOR_SIGNIFICANCE:
            return
        if exp.variant_runs < self.MIN_RUNS_FOR_SIGNIFICANCE:
            return

        # Calculate statistical significance (simplified z-test for proportions)
        winner, p_value = self._calculate_significance(exp)

        if p_value is not None and p_value < self.SIGNIFICANCE_THRESHOLD:
            self._conclude_experiment(experiment_id, winner, p_value)
        elif exp.control_runs >= 30 and exp.variant_runs >= 30:
            # Max runs reached without significance - inconclusive
            self._conclude_experiment(experiment_id, "inconclusive", p_value)

    def _calculate_significance(self, exp: Experiment) -> Tuple[Optional[str], Optional[float]]:
        """Calculate statistical significance between control and variant.

        Uses a simplified z-test for the difference in success rates.
        For quality scores, we'd ideally use a t-test but simplify here.

        Returns:
            (winner, p_value) or (None, None) if can't calculate
        """
        # Compare quality scores (primary metric)
        if exp.control_avg_quality is None or exp.variant_avg_quality is None:
            return None, None

        c_quality = exp.control_avg_quality
        v_quality = exp.variant_avg_quality
        c_n = exp.control_runs
        v_n = exp.variant_runs

        # Approximate standard error (assuming std dev of ~0.2 for quality scores)
        std_dev = 0.2
        se = std_dev * sqrt(1/c_n + 1/v_n)

        if se == 0:
            return None, None

        # Z-score for difference
        z = abs(c_quality - v_quality) / se

        # Approximate p-value (two-tailed)
        # Using normal distribution approximation
        p_value = 2 * (1 - self._normal_cdf(z))

        winner = "variant" if v_quality > c_quality else "control"

        return winner, p_value

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF using error function approximation."""
        # Approximation of the standard normal CDF
        from math import erf
        return 0.5 * (1 + erf(x / sqrt(2)))

    def _conclude_experiment(self, experiment_id: int, winner: str, p_value: Optional[float]):
        """Conclude an experiment and apply the winner."""
        exp = self.get_experiment_by_id(experiment_id)
        if not exp:
            return

        self.db.execute(
            """
            UPDATE experiments SET
                status = 'completed',
                winner = ?,
                statistical_significance = ?,
                ended_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (winner, p_value, experiment_id)
        )

        logger.info(f"Concluded experiment {experiment_id}: winner = {winner}, p = {p_value}")

        # If variant won, activate it
        if winner == "variant":
            self.config_store.activate_version(exp.variant_config_id)
            logger.info(f"Activated winning variant config: {exp.variant_config_id}")

            # Log to change log
            self.db.execute(
                """
                INSERT INTO change_log (action, details, config_version_id, triggered_by)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "experiment_winner_applied",
                    f"Experiment '{exp.name}' completed. Variant won with p={p_value:.4f}",
                    exp.variant_config_id,
                    "experiment_manager"
                )
            )

    def abandon_experiment(self, experiment_id: int, reason: str = "Manual abandonment"):
        """Abandon an experiment without applying changes."""
        self.db.execute(
            """
            UPDATE experiments SET
                status = 'abandoned',
                ended_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (experiment_id,)
        )

        logger.warning(f"Abandoned experiment {experiment_id}: {reason}")

    def get_all_experiments(self, limit: int = 50) -> list[Experiment]:
        """Get all experiments, most recent first."""
        rows = self.db.execute(
            "SELECT * FROM experiments ORDER BY started_at DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_experiment(row) for row in rows]
