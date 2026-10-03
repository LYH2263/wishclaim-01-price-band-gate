"""Immutable band snapshot attached to a wish at creation time.

The snapshot pins the cap in force when the wish was written. Later changes to
the default cap must never recompute it ("不回刷").
"""
import json

SNAPSHOT_VERSION = 1


def build_snapshot(estimate: float, band_mode: str, cap: float,
                   verdict: dict, decided_at: str) -> dict:
    return {
        "version": SNAPSHOT_VERSION,
        "estimate": estimate,
        "band_mode": band_mode,
        "cap": cap,
        "within": verdict["within"],
        "warning": verdict["warning"],
        "decided_at": decided_at,
    }


def dumps(snapshot: dict) -> str:
    return json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))


def loads(text: str | None) -> dict | None:
    if not text:
        return None
    return json.loads(text)
