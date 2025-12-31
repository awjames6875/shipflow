"""
Self-Improving Workflow Optimizer

This package provides autonomous self-improvement for the shipflow workflow:
- MetricsCollector: Captures timing, success/failure, quality for each step
- ConfigStore: Version-controlled prompts and parameters
- ExperimentManager: A/B testing with statistical significance
- ImprovementEngine: Daily analysis, research, and improvement cycle
- RollbackGuard: Auto-reverts bad changes for safety
"""

from .database import Database
from .metrics import MetricsCollector
from .config_store import ConfigStore
from .experiments import ExperimentManager
from .improvement_engine import ImprovementEngine
from .rollback_guard import RollbackGuard

__all__ = [
    "Database",
    "MetricsCollector",
    "ConfigStore",
    "ExperimentManager",
    "ImprovementEngine",
    "RollbackGuard",
]
