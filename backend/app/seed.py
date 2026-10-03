import json

from app.db import connect

WISH_COLS = [
    ("price", "REAL"),
    ("band_mode", "TEXT"),
    ("band_snapshot", "TEXT"),
]


def _migrate_columns(c):
    existing = {r["name"] for r in c.execute("PRAGMA table_info(wishes)")}
    for name, decl in WISH_COLS:
        if name not in existing:
            c.execute(f"ALTER TABLE wishes ADD COLUMN {name} {decl}")


def init_db():
    c = connect()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS wishes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, note TEXT, status TEXT,
      claimer TEXT, claimed_at TEXT, expires_at TEXT, data_quality TEXT,
      price REAL, band_mode TEXT, band_snapshot TEXT
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    """)
    _migrate_columns(c)
    if c.execute("SELECT COUNT(*) c FROM wishes").fetchone()["c"] == 0:
        c.executemany(
            "INSERT INTO wishes(title,note,status,claimer,claimed_at,expires_at,data_quality,"
            "price,band_mode,band_snapshot) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                ("机械键盘", "红轴", "open", None, None, None, "clean",
                 599.0, "soft",
                 json.dumps({"v": 1, "price": 599.0, "mode": "soft", "cap": 500.0,
                             "verdict": "warn", "warning": "OVER_SOFT_CAP"},
                            ensure_ascii=False, sort_keys=True)),
                ("围巾", "羊毛", "open", None, None, None, "clean",
                 120.0, "soft",
                 json.dumps({"v": 1, "price": 120.0, "mode": "soft", "cap": 500.0,
                             "verdict": "ok", "warning": None},
                            ensure_ascii=False, sort_keys=True)),
                ("脏愿望-空标题", "", "open", None, None, None, "dirty",
                 None, None, None),
                ("过期锁样例", "应被TTL释放", "claimed", "ghost", "2020-01-01T00:00:00+00:00",
                 "2020-01-01T01:00:00+00:00", "dirty",
                 300.0, "hard",
                 json.dumps({"v": 1, "price": 300.0, "mode": "hard", "cap": 500.0,
                             "verdict": "ok", "warning": None},
                            ensure_ascii=False, sort_keys=True)),
            ],
        )
        c.execute("INSERT INTO settings(key,value) VALUES ('ttl_seconds','86400')")
        c.execute("INSERT INTO settings(key,value) VALUES ('wall_title','暖粉愿望墙')")
        c.execute("INSERT INTO settings(key,value) VALUES ('price_cap_default','500')")
        c.commit()
    else:
        # 既有库迁移：仅在缺省键时补默认值，绝不回刷用户已维护的现行上限
        row = c.execute("SELECT 1 FROM settings WHERE key='price_cap_default'").fetchone()
        if row is None:
            c.execute("INSERT INTO settings(key,value) VALUES ('price_cap_default','500')")
            c.commit()
    c.close()
