"""写愿望服务：编排 入参校验 -> 读现行默认上限 -> 判定 -> 落库快照。

- hard 超额：返回 reject，绝不执行 INSERT，wishes 不增行。
- soft 超额：照常落库，快照 verdict=warn + warning 枚举码。
- 未填估价（price is None）：不启用带，三列全 NULL，字段集合与改造前兼容。
"""
from .judge import (
    MODE_SOFT, validate_input, judge_band,
)
from .snapshot import get_default_cap, build_snapshot

DEFAULT_MODE = MODE_SOFT


def create_wish(c, title, note, price, mode):
    """返回 {'ok': bool, 'code': 枚举码|None, 'id': int|None, 'warning': 枚举码|None}。"""
    err = validate_input(title, price, mode)
    if err is not None:
        return {"ok": False, "code": err, "id": None, "warning": None}

    if price is None:
        cur = c.execute(
            "INSERT INTO wishes(title,note,status,data_quality,price,band_mode,band_snapshot) "
            "VALUES (?,?,?, ?,NULL,NULL,NULL)",
            (title, note, "open", "clean"),
        )
        return {"ok": True, "code": None, "id": cur.lastrowid, "warning": None}

    eff_mode = mode if mode is not None else DEFAULT_MODE
    cap = get_default_cap(c)
    decision = judge_band(price, eff_mode, cap)
    if decision["verdict"] == "reject":
        # 整单失败：不插行
        return {"ok": False, "code": decision["code"], "id": None, "warning": None}

    snapshot = build_snapshot(price, eff_mode, cap, decision)
    cur = c.execute(
        "INSERT INTO wishes(title,note,status,data_quality,price,band_mode,band_snapshot) "
        "VALUES (?,?,?,?,?,?,?)",
        (title, note, "open", "clean", float(price), eff_mode, snapshot),
    )
    return {
        "ok": True,
        "code": None,
        "id": cur.lastrowid,
        "warning": decision["code"],   # soft 超额时为 OVER_SOFT_CAP，否则 None
    }
