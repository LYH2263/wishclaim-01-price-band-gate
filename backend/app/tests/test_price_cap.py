import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules import price_cap as pc


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Each test gets an isolated sqlite file; startup runs seed.init_db() there.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with TestClient(app) as c:
        yield c


def count_wishes(client):
    return len(client.get("/api/wishes").json())


# ---------- pure judging ----------

def test_validate_estimate_rules():
    assert pc.validate_estimate(None) is None
    assert pc.validate_estimate(1) == 1.0
    with pytest.raises(ValueError, match=pc.ERR_ESTIMATE_NOT_POSITIVE):
        pc.validate_estimate(0)
    with pytest.raises(ValueError, match=pc.ERR_ESTIMATE_NOT_POSITIVE):
        pc.validate_estimate(-3.5)
    with pytest.raises(ValueError, match=pc.ERR_INVALID_ESTIMATE):
        pc.validate_estimate("100")
    with pytest.raises(ValueError, match=pc.ERR_INVALID_ESTIMATE):
        pc.validate_estimate(True)


def test_dirty_title_rejected_by_validator():
    with pytest.raises(ValueError, match=pc.ERR_DIRTY_WISH):
        pc.validate_title("")
    with pytest.raises(ValueError, match=pc.ERR_DIRTY_WISH):
        pc.validate_title("   ")


def test_band_mode_without_estimate_is_ignored():
    assert pc.validate_band_mode("hard", has_estimate=False) is None
    assert pc.validate_band_mode(None, has_estimate=True) == "soft"


def test_judge_soft_hard_within():
    ok = pc.judge(100, "soft", 200)
    assert ok["within"] and ok["warning"] is None and ok["blocked"] is False
    soft = pc.judge(250, "soft", 200)
    assert soft["blocked"] is False and soft["warning"] == pc.WARN_OVER_SOFT_CAP
    hard = pc.judge(250, "hard", 200)
    assert hard["blocked"] is True and hard["code"] == pc.BLOCK_OVER_HARD_CAP
    hard_ok = pc.judge(100, "hard", 200)
    assert hard_ok["within"] and not hard_ok["blocked"]


# ---------- API: legacy-compatible create ----------

def test_create_without_estimate_keeps_legacy_shape(client):
    before = count_wishes(client)
    r = client.post("/api/wishes", json={"title": "围巾", "note": "羊毛"})
    assert r.status_code == 200 and r.json()["warning"] is None
    assert count_wishes(client) == before + 1
    w = client.get(f"/api/wishes/{r.json()['id']}").json()
    assert w["estimate"] is None and w["band_mode"] is None and w["band"] is None
    assert "band_json" not in w


# ---------- soft gate: over cap is stored with warning snapshot ----------

def test_soft_over_cap_persisted_with_warning_snapshot(client):
    before = count_wishes(client)
    r = client.post("/api/wishes", json={"title": "机械键盘", "estimate": 250, "band_mode": "soft"})
    assert r.status_code == 200
    assert r.json()["warning"] == "PRICE_OVER_SOFT_CAP"
    assert count_wishes(client) == before + 1

    w = client.get(f"/api/wishes/{r.json()['id']}").json()
    assert w["data_quality"] == "clean"
    band = w["band"]
    assert band["estimate"] == 250.0 and band["band_mode"] == "soft"
    assert band["cap"] == 200.0 and band["within"] is False
    assert band["warning"] == "PRICE_OVER_SOFT_CAP"
    assert band["decided_at"]


def test_soft_default_mode_when_only_estimate_given(client):
    r = client.post("/api/wishes", json={"title": "礼盒", "estimate": 250})
    assert r.status_code == 200 and r.json()["warning"] == "PRICE_OVER_SOFT_CAP"


# ---------- hard gate: whole order fails, no row appears ----------

def test_hard_over_cap_fails_order_without_row(client):
    before = count_wishes(client)
    r = client.post("/api/wishes", json={"title": "显卡", "estimate": 5000, "band_mode": "hard"})
    assert r.status_code == 422
    assert r.json()["detail"] == "PRICE_OVER_HARD_CAP"
    assert count_wishes(client) == before


def test_invalid_estimate_and_dirty_wish_rejected(client):
    before = count_wishes(client)
    assert client.post("/api/wishes", json={"title": "x", "estimate": 0}).status_code == 422
    assert client.post("/api/wishes", json={"title": "x", "estimate": -1}).status_code == 422
    assert client.post("/api/wishes", json={"title": "x", "estimate": "abc"}).status_code == 422
    r = client.post("/api/wishes", json={"title": "   ", "estimate": 10})
    assert r.status_code == 422 and r.json()["detail"] == "dirty_wish_rejected"
    assert count_wishes(client) == before


# ---------- no recompute + dual-source rules page ----------

def test_cap_change_does_not_rewrite_snapshot_but_applies_to_new_wish(client):
    # 1. wish written under the old default (200)
    old = client.post("/api/wishes", json={"title": "旧愿望", "estimate": 250, "band_mode": "soft"})
    old_id = old.json()["id"]

    # 2. maintain a new current default cap
    upd = client.put("/api/settings/price_cap", json={"cap": 999})
    assert upd.status_code == 200 and upd.json()["default_cap"] == 999.0

    # 3. claimed wishes are not recomputed either
    client.post(f"/api/wishes/{old_id}/claim", json={"claimer": "alice"})

    detail = client.get(f"/api/wishes/{old_id}").json()
    assert detail["band"]["cap"] == 200.0
    assert detail["band"]["warning"] == "PRICE_OVER_SOFT_CAP"

    rules = client.get("/api/rules").json()
    pc_block = rules["price_cap"]
    # source A: current default
    assert pc_block["default_cap"] == 999.0
    assert pc_block["default_source"] == "price_cap_default"
    # source B: per-wish written snapshots, pinned at write time
    written = {row["id"]: row["band"] for row in pc_block["written"]}
    assert written[old_id]["cap"] == 200.0
    assert written[old_id]["warning"] == "PRICE_OVER_SOFT_CAP"
    # legacy wishes without estimate do not appear in the written list
    assert all(b["estimate"] is not None for b in written.values())

    # 4. new wishes eat the new default
    new = client.post("/api/wishes", json={"title": "新愿望", "estimate": 500, "band_mode": "soft"})
    assert new.status_code == 200 and new.json()["warning"] is None
    nw = client.get(f"/api/wishes/{new.json()['id']}").json()
    assert nw["band"]["cap"] == 999.0 and nw["band"]["within"] is True

    # rules page keeps both sources visibly separate after re-fetch
    rules2 = client.get("/api/rules").json()["price_cap"]
    written2 = {row["id"]: row["band"] for row in rules2["written"]}
    assert rules2["default_cap"] == 999.0
    assert written2[old_id]["cap"] == 200.0 and written2[new.json()["id"]]["cap"] == 999.0


# ---------- wall/detail projection parity ----------

def test_wall_badge_and_detail_share_same_snapshot(client):
    wid = client.post("/api/wishes",
                      json={"title": "角标愿望", "estimate": 250, "band_mode": "soft"}).json()["id"]
    wall = next(w for w in client.get("/api/wishes").json() if w["id"] == wid)
    detail = client.get(f"/api/wishes/{wid}").json()
    assert wall["band"] == detail["band"]
    assert wall["band"]["warning"] == "PRICE_OVER_SOFT_CAP"


def test_invalid_cap_update_rejected(client):
    assert client.put("/api/settings/price_cap", json={"cap": 0}).status_code == 422
    assert client.get("/api/rules").json()["price_cap"]["default_cap"] == 200.0
