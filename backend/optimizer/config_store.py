"""
Configuration Store for Self-Improving Workflow

Manages version-controlled configurations for all workflow parameters:
- Prompts (research, script writing)
- Model settings (temperature, model names)
- HeyGen parameters (voice speed, pitch, emotion)

Each change creates a new version, enabling rollback and A/B testing.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

from .database import Database

logger = logging.getLogger(__name__)


@dataclass
class WorkflowConfig:
    """All configurable parameters for the workflow."""
    id: Optional[int] = None
    is_active: bool = False
    is_baseline: bool = False

    # Perplexity config
    perplexity_model: str = "sonar-pro"
    perplexity_recency: str = "day"
    top_10_prompt: str = "Research the top 10 trending news items in my industry from the past 24 hours.\n\n- Industry: {industry}"
    deep_research_prompt: str = """# INSTRUCTIONS

Complete the following tasks, in order:

1. Out of the 10 news stories listed below, select the ONE top news story that is most likely to go viral on social media. It should have broad appeal and contain something unique, controversial, or vitally important information that millions of people should know.

<news>
{top_10_news}
</news>

2. Research more information about the top news story you selected.

3. Your final output should be a detailed report of the top story you've selected. It should be dense with factual data, statistics, sources, and key information based on your research. Include reasons why this story would perform well on social media. Include why a "normal person" in this industry should care about this news."""

    # OpenAI config
    openai_model: str = "o1"
    script_system_prompt: str = """# TASK
1. Analyze the following viral news story:
<news>
{news_report}
</news>

2. Write a conversational monologue script for an AI avatar video, following these guidelines:
   - The script should be approximately 30 seconds when spoken aloud.
   - Include lots of factual details and statistics from the article.
   - Use 6th grade reading level.
   - Balanced viewpoint.
   - First sentence should create an irresistible curiosity gap to hook viewers.
   - Replace the last sentence with this CTA: "Hit follow to stay up to date!"
   - ONLY output the exact video script. Do not output anything else. NEVER include intermediate thoughts, notes, or formatting.

3. Write an SEO-optimized caption that will accompany the video, max 5 hashtags.

4. Write 1 viral sentence, max 8 words, summarizing the content, use 6th grade language, balanced neutral perspective, no emojis, no punctuation except `?` or `!`.

# OUTPUT

You will output structured JSON in the following format:
{{
  "script": "Monologue script to be spoken by AI avatar",
  "caption": "Long SEO-optimized video caption",
  "title": "Short video title"
}}"""
    script_temperature: Optional[float] = None

    # HeyGen config
    heygen_voice_speed: float = 1.1
    heygen_voice_pitch: int = 50
    heygen_voice_emotion: str = "Excited"

    # Metadata
    source: str = "manual"
    parent_version_id: Optional[int] = None
    improvement_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class ConfigStore:
    """Manages versioned workflow configurations."""

    def __init__(self, db: Database):
        self.db = db
        self._ensure_baseline()

    def _ensure_baseline(self):
        """Ensure a baseline config exists."""
        rows = self.db.execute("SELECT id FROM config_versions WHERE is_baseline = 1")
        if not rows:
            self.create_baseline()

    def create_baseline(self) -> int:
        """Create the baseline configuration from defaults."""
        config = WorkflowConfig(is_baseline=True, is_active=True, source="baseline")
        version_id = self._insert_config(config)

        # Log the creation
        self.db.execute(
            "INSERT INTO change_log (action, details, config_version_id, triggered_by) VALUES (?, ?, ?, ?)",
            ("baseline_created", "Initial baseline configuration created", version_id, "system")
        )

        logger.info(f"Created baseline config: version {version_id}")
        return version_id

    def _insert_config(self, config: WorkflowConfig) -> int:
        """Insert a config and return its ID."""
        return self.db.execute_insert(
            """
            INSERT INTO config_versions (
                is_active, is_baseline,
                perplexity_model, perplexity_recency, top_10_prompt, deep_research_prompt,
                openai_model, script_system_prompt, script_temperature,
                heygen_voice_speed, heygen_voice_pitch, heygen_voice_emotion,
                source, parent_version_id, improvement_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1 if config.is_active else 0,
                1 if config.is_baseline else 0,
                config.perplexity_model,
                config.perplexity_recency,
                config.top_10_prompt,
                config.deep_research_prompt,
                config.openai_model,
                config.script_system_prompt,
                config.script_temperature,
                config.heygen_voice_speed,
                config.heygen_voice_pitch,
                config.heygen_voice_emotion,
                config.source,
                config.parent_version_id,
                config.improvement_reason
            )
        )

    def _row_to_config(self, row) -> WorkflowConfig:
        """Convert a database row to WorkflowConfig."""
        return WorkflowConfig(
            id=row["id"],
            is_active=bool(row["is_active"]),
            is_baseline=bool(row["is_baseline"]),
            perplexity_model=row["perplexity_model"],
            perplexity_recency=row["perplexity_recency"],
            top_10_prompt=row["top_10_prompt"],
            deep_research_prompt=row["deep_research_prompt"],
            openai_model=row["openai_model"],
            script_system_prompt=row["script_system_prompt"],
            script_temperature=row["script_temperature"],
            heygen_voice_speed=row["heygen_voice_speed"],
            heygen_voice_pitch=row["heygen_voice_pitch"],
            heygen_voice_emotion=row["heygen_voice_emotion"],
            source=row["source"],
            parent_version_id=row["parent_version_id"],
            improvement_reason=row["improvement_reason"]
        )

    def get_active_config(self) -> WorkflowConfig:
        """Get the currently active configuration."""
        rows = self.db.execute("SELECT * FROM config_versions WHERE is_active = 1 LIMIT 1")
        if rows:
            return self._row_to_config(rows[0])

        # Fallback to baseline
        return self.get_baseline_config()

    def get_baseline_config(self) -> WorkflowConfig:
        """Get the original baseline configuration."""
        rows = self.db.execute("SELECT * FROM config_versions WHERE is_baseline = 1 LIMIT 1")
        if rows:
            return self._row_to_config(rows[0])
        raise RuntimeError("No baseline config found")

    def get_config_by_id(self, version_id: int) -> Optional[WorkflowConfig]:
        """Get a specific config version."""
        rows = self.db.execute("SELECT * FROM config_versions WHERE id = ?", (version_id,))
        if rows:
            return self._row_to_config(rows[0])
        return None

    def create_version(
        self,
        changes: dict,
        source: str,
        reason: str,
        parent_id: Optional[int] = None
    ) -> int:
        """Create a new config version with specific changes.

        Args:
            changes: Dictionary of field names to new values
            source: Where this config came from ('experiment', 'improvement', etc.)
            reason: Why this config was created
            parent_id: Parent version (defaults to current active)

        Returns:
            The new version ID
        """
        # Start from parent or current active config
        if parent_id:
            parent = self.get_config_by_id(parent_id)
        else:
            parent = self.get_active_config()

        if not parent:
            raise RuntimeError("No parent config found")

        # Create new config with changes applied
        config = WorkflowConfig(
            is_active=False,  # New versions start inactive
            is_baseline=False,
            perplexity_model=changes.get("perplexity_model", parent.perplexity_model),
            perplexity_recency=changes.get("perplexity_recency", parent.perplexity_recency),
            top_10_prompt=changes.get("top_10_prompt", parent.top_10_prompt),
            deep_research_prompt=changes.get("deep_research_prompt", parent.deep_research_prompt),
            openai_model=changes.get("openai_model", parent.openai_model),
            script_system_prompt=changes.get("script_system_prompt", parent.script_system_prompt),
            script_temperature=changes.get("script_temperature", parent.script_temperature),
            heygen_voice_speed=changes.get("heygen_voice_speed", parent.heygen_voice_speed),
            heygen_voice_pitch=changes.get("heygen_voice_pitch", parent.heygen_voice_pitch),
            heygen_voice_emotion=changes.get("heygen_voice_emotion", parent.heygen_voice_emotion),
            source=source,
            parent_version_id=parent.id,
            improvement_reason=reason
        )

        version_id = self._insert_config(config)
        logger.info(f"Created config version {version_id}: {reason}")
        return version_id

    def activate_version(self, version_id: int) -> None:
        """Activate a config version (deactivates current)."""
        with self.db.transaction() as conn:
            # Deactivate all configs
            conn.execute("UPDATE config_versions SET is_active = 0")
            # Activate the new one
            conn.execute("UPDATE config_versions SET is_active = 1 WHERE id = ?", (version_id,))
            # Log the change
            conn.execute(
                "INSERT INTO change_log (action, config_version_id, triggered_by) VALUES (?, ?, ?)",
                ("config_activated", version_id, "system")
            )

        logger.info(f"Activated config version: {version_id}")

    def rollback_to_baseline(self) -> int:
        """Emergency rollback to baseline configuration."""
        baseline = self.get_baseline_config()
        if not baseline or not baseline.id:
            raise RuntimeError("No baseline config found")

        with self.db.transaction() as conn:
            # Deactivate all configs
            conn.execute("UPDATE config_versions SET is_active = 0")
            # Activate baseline
            conn.execute("UPDATE config_versions SET is_active = 1 WHERE id = ?", (baseline.id,))
            # Log the rollback
            conn.execute(
                "INSERT INTO change_log (action, details, config_version_id, triggered_by) VALUES (?, ?, ?, ?)",
                ("rollback", "Rolled back to baseline configuration", baseline.id, "rollback_guard")
            )

        logger.warning(f"Rolled back to baseline config: version {baseline.id}")
        return baseline.id

    def get_config_diff(self, v1_id: int, v2_id: int) -> dict:
        """Compare two config versions and return differences."""
        c1 = self.get_config_by_id(v1_id)
        c2 = self.get_config_by_id(v2_id)

        if not c1 or not c2:
            return {}

        diff = {}
        d1, d2 = c1.to_dict(), c2.to_dict()

        for key in d1:
            if key in ("id", "is_active", "is_baseline", "source", "parent_version_id", "improvement_reason"):
                continue
            if d1[key] != d2[key]:
                diff[key] = {"from": d1[key], "to": d2[key]}

        return diff

    def get_recent_versions(self, limit: int = 10) -> list:
        """Get recent config versions."""
        rows = self.db.execute(
            "SELECT * FROM config_versions ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_config(row) for row in rows]

    def get_change_log(self, limit: int = 50) -> list:
        """Get recent change log entries."""
        rows = self.db.execute(
            "SELECT * FROM change_log ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in rows]
