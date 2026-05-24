"""MimirAether / mimicore path resolution (aligned with mimir_constants.get_mimir_home)."""

from __future__ import annotations

import os
import re
from pathlib import Path

_DEFAULT_MIMIR_HOME = Path.home() / ".mimiraether"


def get_mimir_home() -> Path:
    """Runtime data home: MIMIR_AETHER_HOME → MIMIRAETHER_HOME → HERMES_HOME → ~/.mimiraether."""
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME"):
        v = os.getenv(key, "").strip()
        if v:
            return Path(v).expanduser()
    hermes = os.getenv("HERMES_HOME", "").strip()
    if hermes:
        return Path(hermes).expanduser()
    return _DEFAULT_MIMIR_HOME


def get_mimicore_root() -> Path:
    """Root of this mimicore checkout (memory-hall package)."""
    override = os.getenv("MIMICORE_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent


def _tilde_home(path: Path) -> str:
    home = str(Path.home())
    s = str(path)
    if s.startswith(home):
        return "~" + s[len(home) :]
    return s


def memory_vault_data_dir() -> Path:
    return get_mimir_home() / "memory-vault" / "data"


def memory_vault_metadata_dir() -> Path:
    return get_mimir_home() / "memory-vault" / "metadata"


def memory_vault_logs_dir() -> Path:
    return get_mimir_home() / "memory-vault" / "logs"


def default_vault_dir_str() -> str:
    return _tilde_home(memory_vault_data_dir())


def default_log_dir_str() -> str:
    return _tilde_home(memory_vault_logs_dir())


def default_backup_dir_str() -> str:
    return _tilde_home(get_mimir_home() / "workspace" / "memory_backups")


def default_wal_dir_str() -> str:
    return _tilde_home(get_mimicore_root() / "wal")


def default_plugins_dir() -> Path:
    return get_mimicore_root() / "plugins"


def default_mini_agent_results_dir() -> Path:
    return get_mimicore_root() / "mini_agent" / "results"


def fence_violations_log() -> Path:
    return get_mimicore_root() / "fence" / "violations.log"


def audit_project_dir() -> Path:
    return get_mimicore_root() / "audit"


def introspection_log_dirs() -> list[Path]:
    """Canonical log roots first; legacy OpenClaw paths kept for migration scans."""
    home = get_mimir_home()
    legacy = Path.home() / ".openclaw"
    dirs = [
        home / "logs",
        home / "logs" / "gateway",
        legacy / "logs",
        legacy / "workspace" / "logs",
        legacy / "logs" / "gateway",
    ]
    seen: set[str] = set()
    out: list[Path] = []
    for p in dirs:
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def memory_vault_permission_pattern(operation: str) -> str:
    """Permission rule prefix for read:/write: on memory-vault paths."""
    home_tilde = re.escape(_tilde_home(get_mimir_home()) + "/memory-vault/")
    legacy = r"~/\.(?:mimiraether|openclaw)/memory-vault/"
    return rf"^{operation}:(?:{home_tilde}|{legacy})"
