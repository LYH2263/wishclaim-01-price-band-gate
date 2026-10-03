"""价位带判定引擎：纯函数，不碰数据库。

wire 上所有判定结果一律用枚举码（WARN_*/ERR_*），文案由前端唯一字典翻译，
墙卡角标 / 详情 / 规则页三路共用，禁止在后端塞自由文本。
"""
import math

MODE_SOFT = "soft"
MODE_HARD = "hard"
BAND_MODES = (MODE_SOFT, MODE_HARD)

# soft 超额：允许落库，快照打此 warning
WARN_OVER_SOFT_CAP = "OVER_SOFT_CAP"
# hard 超额：整单失败，wishes 不增行
ERR_HARD_CAP_EXCEEDED = "HARD_CAP_EXCEEDED"
ERR_INVALID_PRICE = "INVALID_PRICE"
ERR_INVALID_BAND_MODE = "INVALID_BAND_MODE"
ERR_DIRTY_WISH = "DIRTY_WISH"


def validate_input(title, price, mode):
    """写愿望入参校验。

    返回错误枚举码；None 表示通过。
    - 标题空白 => 脏愿望拒写
    - price 为 None 表示未填估价：不启用价位带，字段集合与改造前兼容
    - price 必须是有限且 >0 的数；mode（若非 None）必须是 soft/hard
    """
    if not isinstance(title, str) or not title.strip():
        return ERR_DIRTY_WISH
    if price is None:
        return None
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return ERR_INVALID_PRICE
    if not math.isfinite(price) or price <= 0:
        return ERR_INVALID_PRICE
    if mode is not None and mode not in BAND_MODES:
        return ERR_INVALID_BAND_MODE
    return None


def judge_band(price, mode, cap):
    """对「已校验通过」的估价做带判定。

    price>0, mode in BAND_MODES；cap 为 None 表示未设默认上限（放行）。
    返回 {verdict: ok|warn|reject, warning, code}：
    - soft 超额 => warn + OVER_SOFT_CAP（调用方照常落库并写快照）
    - hard 超额 => reject + HARD_CAP_EXCEEDED（调用方不得插行）
    """
    if cap is None or price <= cap:
        return {"verdict": "ok", "code": None}
    if mode == MODE_HARD:
        return {"verdict": "reject", "code": ERR_HARD_CAP_EXCEEDED}
    return {"verdict": "warn", "code": WARN_OVER_SOFT_CAP}
