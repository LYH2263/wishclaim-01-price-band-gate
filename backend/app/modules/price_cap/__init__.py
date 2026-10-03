"""Price-band soft/hard gate.

Submodules:
- judge:     input validation + soft/hard decision (pure functions)
- snapshot:  the immutable per-wish band snapshot written at creation time
- store:     current default cap in the settings table
- projection: map persisted wish rows to the wall/detail/rules view models

Warning/block codes are stable enum-like strings, persisted as-is and only
translated to human text in the frontend, so all three projections agree.
"""
from .judge import (
    BAND_SOFT,
    BAND_HARD,
    BAND_MODES,
    WARN_OVER_SOFT_CAP,
    BLOCK_OVER_HARD_CAP,
    ERR_INVALID_ESTIMATE,
    ERR_ESTIMATE_NOT_POSITIVE,
    ERR_INVALID_BAND_MODE,
    ERR_DIRTY_WISH,
    validate_title,
    validate_estimate,
    validate_band_mode,
    judge,
)
from .snapshot import SNAPSHOT_VERSION, build_snapshot, dumps as dumps_snapshot, loads as loads_snapshot
from .store import DEFAULT_CAP, SETTINGS_KEY, default_cap, set_default_cap
from .projection import project_wish, project_band, written_band_rows

__all__ = [
    "BAND_SOFT", "BAND_HARD", "BAND_MODES",
    "WARN_OVER_SOFT_CAP", "BLOCK_OVER_HARD_CAP",
    "ERR_INVALID_ESTIMATE", "ERR_ESTIMATE_NOT_POSITIVE",
    "ERR_INVALID_BAND_MODE", "ERR_DIRTY_WISH",
    "validate_title", "validate_estimate", "validate_band_mode", "judge",
    "SNAPSHOT_VERSION", "build_snapshot", "dumps_snapshot", "loads_snapshot",
    "DEFAULT_CAP", "SETTINGS_KEY", "default_cap", "set_default_cap",
    "project_wish", "project_band", "written_band_rows",
]
