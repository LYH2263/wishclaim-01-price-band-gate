"""价位带快照落库：写入时刻的带判定结果冻结在 wishes.band_snapshot。

快照与现行默认上限（settings.price_cap_default）分源：
- 投影只读快照，改默认上限绝不回刷历史愿望（含已认领）。
- 规则页同时列「现行默认上限」与每条愿望的「写入带」，两源各自独立。
"""
import json

SNAPSHOT_VERSION = 1
SETTING_CAP_KEY = "price_cap_default"


def get_default_cap(c):
    """现行默认上限；未配置返回 None（视为不设限）。"""
    row = c.execute("SELECT value FROM settings WHERE key=?", (SETTING_CAP_KEY,)).fetchone()
    if row is None or row["value"] in (None, ""):
        return None
    return float(row["value"])


def set_default_cap(c, cap):
    """更新现行默认上限（只影响此后新发的愿望）。"""
    c.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (SETTING_CAP_KEY, str(float(cap))),
    )


def build_snapshot(price, mode, cap, decision):
    """冻结写入时刻的带信息。price 已通过校验（>0），decision 来自 judge.judge。

    hard 超额时调用方根本不应插行，故快照 verdict 只会是 ok/warn。
    """
    snap = {
        "v": SNAPSHOT_VERSION,
        "price": float(price),
        "mode": mode,
        "cap": (float(cap) if cap is not None else None),
        "verdict": decision["verdict"],
        "warning": decision["code"] if decision["verdict"] == "warn" else None,
    }
    return json.dumps(snap, ensure_ascii=False, sort_keys=True)


def parse_snapshot(raw):
    """解析快照；无快照（未填估价的历史愿望）或脏数据返回 None。"""
    if not raw:
        return None
    try:
        snap = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(snap, dict) or snap.get("v") != SNAPSHOT_VERSION:
        return None
    return snap
