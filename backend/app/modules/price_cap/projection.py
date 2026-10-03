"""Read-side projection of persisted wishes to wall/detail/rules views.

All three surfaces read the same stored snapshot — none of them recomputes a
band from the current default cap.
"""
from .snapshot import loads


def project_band(row: dict) -> dict | None:
    return loads(row.get("band_json"))


def project_wish(row: dict) -> dict:
    """Wish dict for API responses; band comes solely from the snapshot."""
    out = dict(row)
    out["band"] = loads(out.pop("band_json", None))
    return out


def written_band_rows(c) -> list[dict]:
    """Wishes that were written with an estimate, snapshot attached."""
    rows = c.execute(
        "SELECT * FROM wishes WHERE estimate IS NOT NULL ORDER BY id"
    ).fetchall()
    return [project_wish(dict(r)) for r in rows]
