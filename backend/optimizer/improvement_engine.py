"""
Improvement Engine - The Self-Improving Brain

This is the core intelligence that:
1. Analyzes recent workflow performance using LLM self-reflection
2. Searches the internet for better approaches (Perplexity)
3. Generates improvement hypotheses
4. Creates experiments to test improvements
5. Runs daily to continuously optimize the workflow
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import httpx
from openai import OpenAI

from .database import Database
from .metrics import MetricsCollector
from .config_store import ConfigStore
from .experiments import ExperimentManager

logger = logging.getLogger(__name__)


@dataclass
class ImprovementIdea:
    """A discovered improvement opportunity."""
    source: str  # 'llm_reflection', 'web_search', 'community'
    target_component: str  # 'research', 'script', 'video', 'posting'
    description: str
    rationale: str
    config_change: dict
    expected_improvement: str  # 'quality', 'reliability', 'speed'
    priority_score: float = 0.0


class ImprovementEngine:
    """Daily analysis and improvement cycle."""

    # Priority weights (Quality > Reliability > Speed)
    PRIORITY_WEIGHTS = {
        "quality": 3.0,
        "reliability": 2.0,
        "speed": 1.0
    }

    # Limits for safety
    MAX_EXPERIMENTS_PER_DAY = 3
    MAX_CONFIG_CHANGES_PER_DAY = 3

    def __init__(
        self,
        db: Database,
        metrics: MetricsCollector,
        config_store: ConfigStore,
        experiment_manager: ExperimentManager,
        perplexity_api_key: str,
        openai_api_key: str
    ):
        self.db = db
        self.metrics = metrics
        self.config_store = config_store
        self.experiment_manager = experiment_manager
        self.perplexity_api_key = perplexity_api_key
        self.openai_api_key = openai_api_key
        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

    async def run_daily_cycle(self) -> dict:
        """Execute the full daily improvement cycle.

        Returns a summary of what was done.
        """
        logger.info("=" * 50)
        logger.info("Starting daily improvement cycle")
        logger.info("=" * 50)

        results = {
            "started_at": datetime.now().isoformat(),
            "analysis": None,
            "ideas_found": 0,
            "experiments_created": 0,
            "experiments_concluded": 0,
            "errors": []
        }

        try:
            # Step 1: Analyze recent performance
            logger.info("Step 1: Analyzing recent performance...")
            analysis = await self._analyze_performance()
            results["analysis"] = analysis

            # Step 2: Research improvements based on analysis
            logger.info("Step 2: Researching improvements...")
            ideas = await self._research_improvements(analysis)
            results["ideas_found"] = len(ideas)

            # Step 3: Prioritize ideas
            logger.info("Step 3: Prioritizing ideas...")
            prioritized = self._prioritize_ideas(ideas)

            # Step 4: Create experiments for top ideas
            logger.info("Step 4: Creating experiments...")
            experiments = await self._create_experiments(prioritized[:self.MAX_EXPERIMENTS_PER_DAY])
            results["experiments_created"] = len(experiments)

            # Step 5: Check existing experiments for conclusions
            logger.info("Step 5: Checking existing experiments...")
            concluded = self._check_experiments()
            results["experiments_concluded"] = concluded

        except Exception as e:
            logger.error(f"Error in improvement cycle: {e}")
            results["errors"].append(str(e))

        results["completed_at"] = datetime.now().isoformat()
        logger.info(f"Daily cycle complete: {results}")
        return results

    async def _analyze_performance(self) -> dict:
        """Analyze recent workflow runs using LLM self-reflection."""
        # Get metrics from last 48 hours
        recent_runs = self.metrics.get_recent_runs(hours=48)
        aggregated = self.metrics.get_aggregated_metrics(days=2)

        if not recent_runs:
            return {"status": "no_data", "message": "No recent runs to analyze"}

        # Prepare data for LLM analysis
        metrics_summary = {
            "total_runs": len(recent_runs),
            "success_rate": aggregated.get("success_rate", 0),
            "avg_quality": aggregated.get("avg_quality"),
            "avg_duration_ms": aggregated.get("avg_duration_ms"),
            "failures": [
                {
                    "error_step": r.get("error_step"),
                    "error_message": r.get("error_message")
                }
                for r in recent_runs if r.get("status") == "failed"
            ],
            "step_durations": {
                "research": aggregated.get("avg_research_ms"),
                "script": aggregated.get("avg_script_ms"),
                "video": aggregated.get("avg_video_ms"),
                "posting": aggregated.get("avg_posting_ms")
            }
        }

        if not self.openai_client:
            return {"status": "no_openai", "metrics": metrics_summary}

        # Use LLM to analyze
        prompt = f"""Analyze these workflow execution results and identify:
1. What's working well (keep doing)
2. What's causing failures (fix)
3. What's slow (optimize)
4. Quality issues (improve)

The workflow is: Research news → Write video script → Create AI avatar video → Post to social media

Performance Data:
{json.dumps(metrics_summary, indent=2)}

Output JSON with structure:
{{
  "health_status": "healthy" | "degraded" | "critical",
  "successes": ["things working well..."],
  "failures": [{{"issue": "...", "frequency": N, "root_cause": "..."}}],
  "slow_steps": [{{"step": "...", "avg_ms": N, "optimization": "..."}}],
  "quality_issues": ["..."],
  "improvement_suggestions": [
    {{"component": "research|script|video|posting", "suggestion": "...", "expected_impact": "quality|reliability|speed"}}
  ]
}}"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Fast, cheap model for analysis
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            analysis = json.loads(content)
            analysis["metrics"] = metrics_summary
            return analysis
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {"status": "error", "error": str(e), "metrics": metrics_summary}

    async def _research_improvements(self, analysis: dict) -> List[ImprovementIdea]:
        """Search for improvements using web research and LLM ideas."""
        ideas = []

        # Extract ideas from LLM analysis
        if "improvement_suggestions" in analysis:
            for suggestion in analysis["improvement_suggestions"]:
                idea = self._suggestion_to_idea(suggestion)
                if idea:
                    ideas.append(idea)

        # Search web for solutions to failures
        if analysis.get("failures") and self.perplexity_api_key:
            web_ideas = await self._search_web_for_solutions(analysis)
            ideas.extend(web_ideas)

        # Search for better prompt techniques
        if self.perplexity_api_key:
            prompt_ideas = await self._research_prompt_improvements()
            ideas.extend(prompt_ideas)

        # Store discovered ideas
        for idea in ideas:
            self._save_improvement_idea(idea)

        return ideas

    def _suggestion_to_idea(self, suggestion: dict) -> Optional[ImprovementIdea]:
        """Convert an LLM suggestion to an ImprovementIdea."""
        component = suggestion.get("component", "script")
        suggestion_text = suggestion.get("suggestion", "")
        expected_impact = suggestion.get("expected_impact", "quality")

        # Generate config changes based on component
        config_change = self._generate_config_change(component, suggestion_text)
        if not config_change:
            return None

        return ImprovementIdea(
            source="llm_reflection",
            target_component=component,
            description=suggestion_text[:100],
            rationale=suggestion_text,
            config_change=config_change,
            expected_improvement=expected_impact
        )

    def _generate_config_change(self, component: str, suggestion: str) -> Optional[dict]:
        """Generate config changes based on suggestion.

        This is where we map high-level suggestions to specific config changes.
        """
        suggestion_lower = suggestion.lower()

        # Script improvements
        if component == "script":
            if "hook" in suggestion_lower or "attention" in suggestion_lower:
                return {
                    "script_system_prompt": self._enhance_prompt_hook()
                }
            if "shorter" in suggestion_lower or "concise" in suggestion_lower:
                return {
                    "script_system_prompt": self._enhance_prompt_concise()
                }

        # Video improvements
        if component == "video":
            if "energy" in suggestion_lower or "excitement" in suggestion_lower:
                return {"heygen_voice_speed": 1.2, "heygen_voice_emotion": "Excited"}
            if "calm" in suggestion_lower or "professional" in suggestion_lower:
                return {"heygen_voice_speed": 1.0, "heygen_voice_emotion": "Friendly"}

        # Research improvements
        if component == "research":
            if "recent" in suggestion_lower or "fresh" in suggestion_lower:
                return {"perplexity_recency": "hour"}

        return None

    def _enhance_prompt_hook(self) -> str:
        """Return an enhanced script prompt focused on better hooks."""
        current = self.config_store.get_active_config()
        # Add hook enhancement
        enhanced = current.script_system_prompt.replace(
            "First sentence should create an irresistible curiosity gap to hook viewers.",
            "First sentence MUST create an irresistible curiosity gap to hook viewers. Use one of these proven hook patterns: 1) Shocking statistic, 2) Unexpected question, 3) Bold claim, 4) Time-sensitive urgency."
        )
        return enhanced

    def _enhance_prompt_concise(self) -> str:
        """Return an enhanced script prompt focused on conciseness."""
        current = self.config_store.get_active_config()
        enhanced = current.script_system_prompt.replace(
            "The script should be approximately 30 seconds when spoken aloud.",
            "The script should be EXACTLY 25-30 seconds when spoken aloud. Be ruthlessly concise. Every word must earn its place."
        )
        return enhanced

    async def _search_web_for_solutions(self, analysis: dict) -> List[ImprovementIdea]:
        """Use Perplexity to search for solutions to identified issues."""
        ideas = []

        failures = analysis.get("failures", [])
        if not failures:
            return ideas

        # Build search query from failures
        issues = [f.get("issue", "") for f in failures[:3]]
        issues_text = ", ".join(issues)

        prompt = f"""I'm building an AI video generation pipeline with these steps:
1. Perplexity AI research (trending news)
2. OpenAI script writing (viral video scripts)
3. HeyGen avatar video creation
4. Blotato social media posting

Current issues: {issues_text}

Search for:
- Best practices for AI video scripts that go viral
- Prompt engineering techniques for better content
- API reliability patterns for production systems
- HeyGen optimization tips

Return 3-5 specific, actionable improvements with clear implementation steps."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.perplexity_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "sonar-pro",
                        "messages": [{"role": "user", "content": prompt}],
                        "search_recency_filter": "month"
                    }
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Parse ideas from response (simplified)
                # In production, use structured output or better parsing
                idea = ImprovementIdea(
                    source="web_search",
                    target_component="script",
                    description="Web research suggestions",
                    rationale=content[:500],
                    config_change={},  # Would need LLM to convert to config
                    expected_improvement="quality"
                )
                ideas.append(idea)

        except Exception as e:
            logger.error(f"Web search failed: {e}")

        return ideas

    async def _research_prompt_improvements(self) -> List[ImprovementIdea]:
        """Search for better prompt engineering techniques."""
        if not self.perplexity_api_key:
            return []

        prompt = """Search for the latest prompt engineering techniques (2024-2025) for:
1. Writing viral social media video scripts
2. Creating engaging hooks and CTAs
3. Optimizing content for short-form video platforms

Focus on specific techniques that can be immediately applied.
Return actionable prompt templates or patterns."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.perplexity_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "sonar-pro",
                        "messages": [{"role": "user", "content": prompt}],
                        "search_recency_filter": "month"
                    }
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Create improvement idea
                return [ImprovementIdea(
                    source="web_search",
                    target_component="script",
                    description="Prompt engineering improvements from web research",
                    rationale=content[:500],
                    config_change={},
                    expected_improvement="quality"
                )]

        except Exception as e:
            logger.error(f"Prompt research failed: {e}")
            return []

    def _prioritize_ideas(self, ideas: List[ImprovementIdea]) -> List[ImprovementIdea]:
        """Score and rank improvement ideas."""
        for idea in ideas:
            idea.priority_score = self.PRIORITY_WEIGHTS.get(idea.expected_improvement, 1.0)

            # Boost ideas with concrete config changes
            if idea.config_change:
                idea.priority_score *= 1.5

        return sorted(ideas, key=lambda x: x.priority_score, reverse=True)

    async def _create_experiments(self, ideas: List[ImprovementIdea]) -> list:
        """Create A/B experiments for top ideas."""
        experiments = []

        for idea in ideas:
            if not idea.config_change:
                continue

            if not self.experiment_manager.can_create_experiment():
                logger.info("Max concurrent experiments reached, skipping remaining ideas")
                break

            try:
                exp = self.experiment_manager.create_experiment(
                    name=f"Test: {idea.description[:50]}",
                    hypothesis=idea.rationale[:200],
                    variant_changes=idea.config_change
                )
                experiments.append(exp)

                # Update improvement record
                self.db.execute(
                    "UPDATE improvements SET status = 'testing', experiment_id = ? WHERE id = (SELECT MAX(id) FROM improvements WHERE description = ?)",
                    (exp.id, idea.description)
                )

            except Exception as e:
                logger.error(f"Failed to create experiment for idea: {e}")

        return experiments

    def _check_experiments(self) -> int:
        """Check running experiments and count concluded ones."""
        running = self.experiment_manager.get_running_experiments()
        concluded = 0

        for exp in running:
            # The experiment manager checks significance on each run result
            # This is just for logging
            if exp.status == "completed":
                concluded += 1

        return concluded

    def _save_improvement_idea(self, idea: ImprovementIdea):
        """Save an improvement idea to the database."""
        self.db.execute_insert(
            """
            INSERT INTO improvements (source, target_component, description, rationale, config_change_json, expected_improvement, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                idea.source,
                idea.target_component,
                idea.description,
                idea.rationale,
                json.dumps(idea.config_change) if idea.config_change else None,
                idea.expected_improvement
            )
        )

    def get_recent_improvements(self, limit: int = 20) -> list:
        """Get recent improvement ideas."""
        rows = self.db.execute(
            "SELECT * FROM improvements ORDER BY discovered_at DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in rows]

    def get_improvement_stats(self) -> dict:
        """Get statistics about improvements."""
        rows = self.db.execute("""
            SELECT
                status,
                COUNT(*) as count,
                AVG(actual_impact_quality) as avg_quality_impact,
                AVG(actual_impact_reliability) as avg_reliability_impact,
                AVG(actual_impact_speed) as avg_speed_impact
            FROM improvements
            GROUP BY status
        """)
        return {row["status"]: dict(row) for row in rows}
