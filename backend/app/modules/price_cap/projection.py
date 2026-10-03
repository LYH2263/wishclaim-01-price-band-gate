"""价位带投影：墙卡角标 / 详情 band / 规则页写入带三路共用。

铁律：只从落库的 band_snapshot 投影，绝不拿现行默认上限重算历史愿望
（否则已认领愿望的带会被新默认回刷）。
"""
from .snapshot import parse_snapshot


def project_band(row):
    """从一行 wish（dict 或 sqlite Row）投影出带视图；无快照返回 None。"""
    snap = parse_snapshot(row["band_snapshot"] if "band_snapshot" in row.keys() else None)
    if snap is None:
        return None
    return {
        "price": snap["price"],
        "mode": snap["mode"],
        "cap": snap["cap"],
        "verdict": snap["verdict"],          # ok | warn
        "warning": snap["warning"],          # 枚举码，如 OVER_SOFT_CAP；无则 None
    }


def project_row(row):
    """整条 wish 行 + 统一 band 投影，供 list/get/mine/done 返回。"""
    d = dict(row)
    d["band"] = project_band(row)
    return d
