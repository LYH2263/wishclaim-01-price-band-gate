"""Current default price cap, sourced from the settings table.

This is a separate source from per-wish snapshots: changing it affects only
newly created wishes ("新发愿望才吃新默认").
"""

DEFAULT_CAP = 200.0
SETTINGS_KEY = "price_cap_default"


def default_cap(c) -> float:
    row = c.execute("SELECT value FROM settings WHERE key=?", (SETTINGS_KEY,)).fetchone()
    return float(row["value"]) if row else DEFAULT_CAP


def set_default_cap(c, cap: float) -> None:
    c.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (SETTINGS_KEY, str(float(cap))),
    )
