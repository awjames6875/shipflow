"""
Workflow Wrapper - Integrates the optimizer with the main workflow

This module provides a wrapper that:
1. Collects metrics for each workflow step
2. Uses versioned configurations
3. Participates in A/B experiments
4. Triggers rollback checks before runs
"""

import logging
from typing import Optional
from openai import OpenAI

from .database import Database
from .metrics import MetricsCollector
from .config_store import ConfigStore, WorkflowConfig
from .experiments import ExperimentManager
from .rollback_guard import RollbackGuard

logger = logging.getLogger(__name__)


class OptimizedWorkflow:
    """Wraps the workflow with optimization features."""

    def __init__(
        self,
        db: Database,
        metrics: MetricsCollector,
        config_store: ConfigStore,
        experiment_manager: ExperimentManager,
        rollback_guard: RollbackGuard,
        openai_api_key: Optional[str] = None
    ):
        self.db = db
        self.metrics = metrics
        self.config_store = config_store
        self.experiment_manager = experiment_manager
        self.rollback_guard = rollback_guard
        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

    def pre_run_setup(self, industry: str) -> tuple:
        """Set up for a workflow run.

        Returns:
            (run_id, config, experiment_id, experiment_variant)
        """
        # Check health and rollback if needed
        ok, msg = self.rollback_guard.pre_run_check()
        if msg != "OK":
            logger.warning(f"Pre-run check: {msg}")

        # Get config for this run (may be from experiment)
        config_id, experiment_id, variant = self.experiment_manager.get_config_for_run()
        config = self.config_store.get_config_by_id(config_id)

        if not config:
            config = self.config_store.get_active_config()

        # Start metrics collection
        run_id = self.metrics.start_run(
            industry=industry,
            config_version_id=config.id,
            experiment_id=experiment_id,
            experiment_variant=variant
        )

        return run_id, config, experiment_id, variant

    def post_run_complete(
        self,
        status: str,
        experiment_id: Optional[int] = None,
        variant: Optional[str] = None
    ):
        """Complete a workflow run and update experiment if applicable."""
        # Complete metrics
        self.metrics.complete_run(status)

        # Update experiment results if this was part of one
        if experiment_id and variant:
            run = self.metrics.current_run
            if run:
                self.experiment_manager.record_run_result(
                    experiment_id=experiment_id,
                    variant=variant,
                    success=(status == "completed"),
                    quality_score=run.script_quality_score,
                    duration_ms=int((run.completed_at - run.started_at).total_seconds() * 1000) if run.completed_at else 0
                )

    async def evaluate_script_quality(self, script: str) -> float:
        """Use LLM to evaluate script quality (0-1 scale)."""
        if not self.openai_client:
            return 0.5  # Default if no OpenAI

        prompt = f"""Rate this video script on a scale of 0 to 1 for viral potential.

Consider:
- Hook strength (is the first sentence attention-grabbing?)
- Information density (facts, statistics, value)
- Readability (6th grade level, easy to understand)
- CTA effectiveness (clear call to action)
- Engagement potential (would this make people comment/share?)

Script:
{script[:1000]}

Output ONLY a decimal number between 0 and 1, nothing else."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap for evaluation
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10
            )
            content = response.choices[0].message.content.strip()
            score = float(content)
            return max(0.0, min(1.0, score))
        except Exception as e:
            logger.error(f"Quality evaluation failed: {e}")
            return 0.5

    def get_formatted_prompts(self, config: WorkflowConfig, industry: str, top_10_news: str = "", news_report: str = "") -> dict:
        """Get formatted prompts from config with variables filled in."""
        return {
            "top_10_prompt": config.top_10_prompt.format(industry=industry),
            "deep_research_prompt": config.deep_research_prompt.format(
                industry=industry,
                top_10_news=top_10_news
            ),
            "script_prompt": config.script_system_prompt.format(
                news_report=news_report
            )
        }
