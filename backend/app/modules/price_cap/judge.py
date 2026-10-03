"""Band judging: validate wish input and decide soft/hard gate result.

Pure logic, no DB access. Codes raised/returned here are the contract shared
by the API and the wall/detail/rules projections.
"""
from numbers import Real

BAND_SOFT = "soft"
BAND_HARD = "hard"
BAND_MODES = (BAND_SOFT, BAND_HARD)

# Persisted enum codes — never store free-text warnings.
WARN_OVER_SOFT_CAP = "PRICE_OVER_SOFT_CAP"
BLOCK_OVER_HARD_CAP = "PRICE_OVER_HARD_CAP"

ERR_INVALID_ESTIMATE = "invalid_estimate"
ERR_ESTIMATE_NOT_POSITIVE = "estimate_must_be_positive"
ERR_INVALID_BAND_MODE = "invalid_band_mode"
ERR_DIRTY_WISH = "dirty_wish_rejected"


def validate_title(title) -> str:
    """A wish with missing/blank title is dirty and must never be written."""
    if not isinstance(title, str) or not title.strip():
        raise ValueError(ERR_DIRTY_WISH)
    return title


def validate_estimate(estimate) -> float | None:
    """None means 'not filled' (legacy-compatible field set); else > 0."""
    if estimate is None:
        return None
    # bool is a Real subclass; reject it explicitly.
    if isinstance(estimate, bool) or not isinstance(estimate, Real):
        raise ValueError(ERR_INVALID_ESTIMATE)
    value = float(estimate)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(ERR_INVALID_ESTIMATE)
    if value <= 0:
        raise ValueError(ERR_ESTIMATE_NOT_POSITIVE)
    return value


def validate_band_mode(mode, has_estimate: bool) -> str | None:
    """Without an estimate, band_mode is ignored (legacy shape). Default soft."""
    if not has_estimate:
        return None
    if mode is None:
        return BAND_SOFT
    if mode not in BAND_MODES:
        raise ValueError(ERR_INVALID_BAND_MODE)
    return mode


def judge(estimate: float, band_mode: str, cap: float) -> dict:
    """Compare estimate against the cap in force at write time.

    Returns {within, warning, blocked, code}:
    - within cap:           open gate, no warning
    - over cap, soft:       open gate, warning snapshot code
    - over cap, hard:       closed gate, whole order must fail (no row)
    """
    if estimate <= cap:
        return {"within": True, "warning": None, "blocked": False, "code": None}
    if band_mode == BAND_HARD:
        return {"within": False, "warning": None, "blocked": True,
                "code": BLOCK_OVER_HARD_CAP}
    return {"within": False, "warning": WARN_OVER_SOFT_CAP, "blocked": False,
            "code": WARN_OVER_SOFT_CAP}
