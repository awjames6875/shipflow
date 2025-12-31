"""
SQLite Database for the Self-Improving Workflow Optimizer

Tables:
- workflow_runs: Track every workflow execution with metrics
- config_versions: Version-controlled configuration history
- experiments: A/B test definitions and results
- improvements: Discovered optimization ideas
- change_log: Audit trail of all changes
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

# Default database path
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "optimizer.db")


class Database:
    """SQLite database manager for the optimizer."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_dir()
        self._init_schema()

    def _ensure_dir(self):
        """Ensure the data directory exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        """Context manager for transactions."""
        with self.connection() as conn:
            yield conn

    def execute(self, sql: str, params: tuple = ()) -> list:
        """Execute SQL and return results."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()

    def execute_insert(self, sql: str, params: tuple = ()) -> int:
        """Execute INSERT and return last row id."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.lastrowid

    def _init_schema(self):
        """Initialize database schema."""
        with self.connection() as conn:
            conn.executescript(SCHEMA)


SCHEMA = """
-- Track every workflow execution
CREATE TABLE IF NOT EXISTS workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    status TEXT NOT NULL DEFAULT 'running',
    config_version_id INTEGER,
    industry TEXT,

    -- Quality metrics
    script_quality_score REAL,
    video_generated INTEGER DEFAULT 0,
    platforms_posted INTEGER DEFAULT 0,
    platforms_failed INTEGER DEFAULT 0,

    -- Performance metrics (milliseconds)
    total_duration_ms INTEGER,
    research_duration_ms INTEGER,
    script_duration_ms INTEGER,
    video_duration_ms INTEGER,
    posting_duration_ms INTEGER,

    -- Error tracking
    error_step TEXT,
    error_message TEXT,

    -- Experiment tracking
    experiment_id INTEGER,
    experiment_variant TEXT,

    FOREIGN KEY (config_version_id) REFERENCES config_versions(id),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

-- Version-controlled configuration
CREATE TABLE IF NOT EXISTS config_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 0,
    is_baseline INTEGER DEFAULT 0,

    -- Perplexity config
    perplexity_model TEXT DEFAULT 'sonar-pro',
    perplexity_recency TEXT DEFAULT 'day',
    top_10_prompt TEXT,
    deep_research_prompt TEXT,

    -- OpenAI config
    openai_model TEXT DEFAULT 'o1',
    script_system_prompt TEXT,
    script_temperature REAL,

    -- HeyGen config
    heygen_voice_speed REAL DEFAULT 1.1,
    heygen_voice_pitch INTEGER DEFAULT 50,
    heygen_voice_emotion TEXT DEFAULT 'Excited',

    -- Metadata
    source TEXT DEFAULT 'manual',
    parent_version_id INTEGER,
    improvement_reason TEXT,

    FOREIGN KEY (parent_version_id) REFERENCES config_versions(id)
);

-- A/B experiments
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    hypothesis TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    status TEXT DEFAULT 'running',

    control_config_id INTEGER NOT NULL,
    variant_config_id INTEGER NOT NULL,

    -- Results
    control_runs INTEGER DEFAULT 0,
    variant_runs INTEGER DEFAULT 0,
    control_success_rate REAL,
    variant_success_rate REAL,
    control_avg_quality REAL,
    variant_avg_quality REAL,
    control_avg_duration_ms INTEGER,
    variant_avg_duration_ms INTEGER,

    winner TEXT,
    statistical_significance REAL,

    FOREIGN KEY (control_config_id) REFERENCES config_versions(id),
    FOREIGN KEY (variant_config_id) REFERENCES config_versions(id)
);

-- Research findings and improvement ideas
CREATE TABLE IF NOT EXISTS improvements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    source TEXT,

    target_component TEXT,
    description TEXT,
    rationale TEXT,

    -- Implementation
    status TEXT DEFAULT 'pending',
    experiment_id INTEGER,
    config_change_json TEXT,

    -- Evaluation
    expected_improvement TEXT,
    actual_impact_quality REAL,
    actual_impact_reliability REAL,
    actual_impact_speed REAL,

    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

-- Audit log for all changes
CREATE TABLE IF NOT EXISTS change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL,
    details TEXT,
    config_version_id INTEGER,
    triggered_by TEXT DEFAULT 'system',

    FOREIGN KEY (config_version_id) REFERENCES config_versions(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_workflow_runs_started_at ON workflow_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);
CREATE INDEX IF NOT EXISTS idx_config_versions_active ON config_versions(is_active);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
"""
