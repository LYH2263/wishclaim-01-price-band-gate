"""价位带软硬门禁测例。

覆盖：
- judge 纯判定：soft 超额 warn / hard 超额 reject / 估价≤0、脏愿望、坏模式拒写
- 落库：soft 写 warning 快照；hard 整单失败 wishes 不增行
- 不回刷：改现行默认上限后，历史愿望（含已认领）写入带不变
- 双源分列：/api/price-cap（现行默认）与 /api/price-cap/bands（写入快照）独立
- 未填估价：字段集合与改造前兼容，无 band
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import seed
from app.db import connect
from app.modules.price_cap import judge
from app.modules.price_cap.judge import (
    WARN_OVER_SOFT_CAP, ERR_HARD_CAP_EXCEEDED,
    ERR_INVALID_PRICE, ERR_INVALID_BAND_MODE, ERR_DIRTY_WISH,
)
from app.modules.price_cap.snapshot import parse_snapshot
from app.modules.price_cap.projection import project_row


# ---------- judge 纯函数 ----------

def test_judge_in_band_ok():
    assert judge.judge_band(100, judge.MODE_SOFT, 500)["verdict"] == "ok"
    assert judge.judge_band(500, judge.MODE_HARD, 500)["verdict"] == "ok"

def test_judge_soft_over_warns_with_enum():
    r = judge.judge_band(501, judge.MODE_SOFT, 500)
    assert r["verdict"] == "warn" and r["code"] == WARN_OVER_SOFT_CAP

def test_judge_hard_over_rejects_with_enum():
    r = judge.judge_band(501, judge.MODE_HARD, 500)
    assert r["verdict"] == "reject" and r["code"] == ERR_HARD_CAP_EXCEEDED

def test_judge_no_cap_means_unlimited():
    assert judge.judge_band(9_999_999, judge.MODE_HARD, None)["verdict"] == "ok"

@pytest.mark.parametrize("price", [0, -1, -0.01, float("nan"), float("inf"), "100", True])
def test_validate_rejects_bad_price(price):
    assert judge.validate_input("t", price, judge.MODE_SOFT) == ERR_INVALID_PRICE

@pytest.mark.parametrize("title", ["", "   ", None, 123])
def test_validate_rejects_dirty_wish(title):
    assert judge.validate_input(title, 10, judge.MODE_SOFT) == ERR_DIRTY_WISH

def test_validate_rejects_bad_mode():
    assert judge.validate_input("t", 10, "weird") == ERR_INVALID_BAND_MODE

def test_validate_missing_price_is_compatible():
    assert judge.validate_input("t", None, None) is None


# ---------- API + DB（每个用例独立库） ----------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with TestClient(app) as c:
        yield c


def _count(c):
    conn = connect()
    n = conn.execute("SELECT COUNT(*) n FROM wishes").fetchone()["n"]
    conn.close()
    return n


SEED_ROWS = 4


def test_soft_over_persists_with_warning_snapshot(client):
    r = client.post("/api/wishes", json={"title": "软超", "price": 800, "band_mode": "soft"})
    assert r.status_code == 200 and r.json()["warning"] == WARN_OVER_SOFT_CAP
    wid = r.json()["id"]
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["band"]["verdict"] == "warn"
    assert w["band"]["warning"] == WARN_OVER_SOFT_CAP
    assert w["band"]["cap"] == 500 and w["band"]["price"] == 800
    # 快照确实落库，且三路同源
    conn = connect()
    raw = conn.execute("SELECT band_snapshot FROM wishes WHERE id=?", (wid,)).fetchone()["band_snapshot"]
    conn.close()
    snap = parse_snapshot(raw)
    assert snap["warning"] == WARN_OVER_SOFT_CAP and snap["cap"] == 500


def test_hard_over_fails_entire_order_and_inserts_no_row(client):
    before = _count(client)
    assert before == SEED_ROWS
    r = client.post("/api/wishes", json={"title": "硬超", "price": 800, "band_mode": "hard"})
    assert r.status_code == 422 and r.json()["detail"] == ERR_HARD_CAP_EXCEEDED
    assert _count(client) == SEED_ROWS  # wishes 不增行
    # 标题也没有残留
    titles = [w["title"] for w in client.get("/api/wishes").json()]
    assert "硬超" not in titles


def test_bad_price_and_dirty_wish_rejected(client):
    assert client.post("/api/wishes", json={"title": "x", "price": 0}).status_code == 400
    assert client.post("/api/wishes", json={"title": "x", "price": -5}).status_code == 400
    assert client.post("/api/wishes", json={"title": "  ", "price": 10}).status_code == 400
    assert client.post("/api/wishes",
                       json={"title": "x", "price": 10, "band_mode": "mid"}).status_code == 400
    assert _count(client) == SEED_ROWS


def test_missing_price_stays_legacy_compatible(client):
    r = client.post("/api/wishes", json={"title": "无估价", "note": "n"})
    assert r.status_code == 200 and r.json()["warning"] is None
    wid = r.json()["id"]
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["band"] is None and w["price"] is None and w["band_mode"] is None


def test_cap_change_does_not_rebrush_existing_or_claimed(client):
    # 一条 soft 超额（500 上限下），随后改上限到 5000，并认领该愿望
    wid = client.post("/api/wishes",
                      json={"title": "冻结", "price": 800, "band_mode": "soft"}).json()["id"]
    assert client.post(f"/api/wishes/{wid}/claim",
                       json={"claimer": "alice"}).status_code == 200
    client.put("/api/price-cap", json={"cap": 5000})

    w = client.get(f"/api/wishes/{wid}").json()
    # 已认领愿望的带仍是写入时的 500 / warn，绝不被重算成现行 5000 / ok
    assert w["status"] == "claimed"
    assert w["band"]["cap"] == 500
    assert w["band"]["verdict"] == "warn"
    assert w["band"]["warning"] == WARN_OVER_SOFT_CAP

    # 墙路与规则写入带路同样冻结
    wall = [x for x in client.get("/api/wishes").json() if x["id"] == wid][0]
    assert wall["band"]["cap"] == 500 and wall["band"]["warning"] == WARN_OVER_SOFT_CAP
    bands_row = [b for b in client.get("/api/price-cap/bands").json() if b["id"] == wid][0]
    assert bands_row["band"]["cap"] == 500


def test_dual_sources_listed_separately(client):
    # 写入带（历史快照源）
    client.post("/api/wishes", json={"title": "老愿望", "price": 800, "band_mode": "soft"})
    # 改现行默认（settings 源）
    client.put("/api/price-cap", json={"cap": 300})

    current = client.get("/api/price-cap").json()
    assert current["cap"] == 300  # 现行默认已是 300

    bands = client.get("/api/price-cap/bands").json()
    old = [b for b in bands if b["title"] == "老愿望"][0]
    # 写入带保留发布时的 500，而非现行 300 —— 两源分列
    assert old["band"]["cap"] == 500
    caps_in_bands = {b["band"]["cap"] for b in bands}
    assert 300 not in caps_in_bands  # 现行默认不得渗进写入带列表

    # 未填估价的愿望不出现在写入带列表
    no_price_id = client.post("/api/wishes", json={"title": "无带"}).json()["id"]
    bands_ids = {b["id"] for b in client.get("/api/price-cap/bands").json()}
    assert no_price_id not in bands_ids


def test_new_cap_only_applies_to_new_wishes(client):
    client.put("/api/price-cap", json={"cap": 100})
    # 新默认下，150 走 hard 必须被拒；改之前 500 的老愿望不受影响
    r = client.post("/api/wishes", json={"title": "新硬超", "price": 150, "band_mode": "hard"})
    assert r.status_code == 422 and r.json()["detail"] == ERR_HARD_CAP_EXCEEDED
    r2 = client.post("/api/wishes", json={"title": "新软超", "price": 150, "band_mode": "soft"})
    assert r2.status_code == 200 and r2.json()["warning"] == WARN_OVER_SOFT_CAP
    new_band = client.get(f"/api/wishes/{r2.json()['id']}").json()["band"]
    assert new_band["cap"] == 100


def test_put_invalid_cap_rejected(client):
    assert client.put("/api/price-cap", json={"cap": 0}).status_code == 400
    assert client.get("/api/price-cap").json()["cap"] == 500  # 未被改写


def test_projection_reads_only_snapshot_not_current_cap():
    import os, tempfile
    d = tempfile.mkdtemp()
    os.environ["DATA_DIR"] = d
    try:
        seed.init_db()
        conn = connect()
        conn.execute(
            "INSERT INTO wishes(title,note,status,data_quality,price,band_mode,band_snapshot) "
            "VALUES (?,?,?,?,?,?,?)",
            ("手工", "", "open", "clean", 800.0, "soft",
             '{"v":1,"price":800.0,"mode":"soft","cap":500.0,"verdict":"warn","warning":"OVER_SOFT_CAP"}'),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM wishes WHERE title='手工'").fetchone()
        proj = project_row(row)
        conn.close()
        assert proj["band"]["cap"] == 500 and proj["band"]["warning"] == "OVER_SOFT_CAP"
    finally:
        os.environ.pop("DATA_DIR", None)
