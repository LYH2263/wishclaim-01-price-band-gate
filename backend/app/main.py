import math
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.engines.claim_lock import claim_allowed, lock_payload, release_if_expired
from app.modules.price_cap import (
    create_wish, get_default_cap, set_default_cap, project_row,
)
from app.modules.price_cap.judge import (
    BAND_MODES, ERR_DIRTY_WISH, ERR_INVALID_PRICE, ERR_INVALID_BAND_MODE,
)

app = FastAPI(title="Wishclaim", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup(): seed.init_db()

def now(): return datetime.now(timezone.utc)

def ttl():
    c = connect(); row = c.execute("SELECT value FROM settings WHERE key='ttl_seconds'").fetchone(); c.close()
    return int(row["value"] if row else 86400)

def sweep(c):
    for r in c.execute("SELECT * FROM wishes WHERE status='claimed'"):
        rel = release_if_expired(r["status"], r["expires_at"], now())
        if rel:
            c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=? WHERE id=?",
                      (rel["status"], None, None, None, r["id"]))

def _rows(c, sql, args=()):
    return [project_row(r) for r in c.execute(sql, args)]

@app.get("/api/health")
def health(): return {"ok": True, "project": "wishclaim"}

@app.get("/api/wishes")
def list_wishes():
    c = connect(); sweep(c); c.commit()
    rows = _rows(c, "SELECT * FROM wishes ORDER BY id DESC"); c.close(); return rows

@app.get("/api/wishes/{wid}")
def get_wish(wid: int):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    out = project_row(r); c.close(); return out

class WishIn(BaseModel):
    title: str
    note: str = ""
    price: float | None = None      # 未填估价 => None，字段集合与改造前兼容
    band_mode: str | None = None    # None/soft/hard；填了估价默认 soft

_BAD_REQUEST = {ERR_DIRTY_WISH, ERR_INVALID_PRICE, ERR_INVALID_BAND_MODE}

@app.post("/api/wishes")
def create(body: WishIn):
    c = connect()
    before = c.execute("SELECT COUNT(*) n FROM wishes").fetchone()["n"]
    res = create_wish(c, body.title, body.note, body.price, body.band_mode)
    if not res["ok"]:
        c.rollback(); after = c.execute("SELECT COUNT(*) n FROM wishes").fetchone()["n"]; c.close()
        assert after == before, "hard reject must not insert a row"
        status = 400 if res["code"] in _BAD_REQUEST else 422
        raise HTTPException(status, res["code"])
    c.commit(); wid = res["id"]; warning = res["warning"]; c.close()
    return {"id": wid, "warning": warning}

class ClaimIn(BaseModel):
    claimer: str

@app.post("/api/wishes/{wid}/claim")
def claim(wid: int, body: ClaimIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    allowed = claim_allowed(r["status"], r["claimer"], now(), r["expires_at"])
    if not allowed["ok"]:
        c.close(); raise HTTPException(409, allowed["reason"])
    p = lock_payload(body.claimer, now(), ttl())
    c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=? WHERE id=?",
              (p["status"], p["claimer"], p["claimed_at"], p["expires_at"], wid))
    c.commit(); c.close(); return p

@app.post("/api/wishes/{wid}/release")
def release(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "not_claimed")
    c.execute("UPDATE wishes SET status='released', claimer=NULL, claimed_at=NULL, expires_at=NULL WHERE id=?", (wid,))
    c.commit(); c.close(); return {"ok": True, "status": "released"}

@app.post("/api/wishes/{wid}/fulfill")
def fulfill(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "need_claim")
    c.execute("UPDATE wishes SET status='fulfilled' WHERE id=?", (wid,))
    c.commit(); c.close(); return {"ok": True, "status": "fulfilled"}

@app.get("/api/mine")
def mine(claimer: str):
    c = connect(); sweep(c); c.commit()
    rows = _rows(c, "SELECT * FROM wishes WHERE claimer=?", (claimer,)); c.close(); return rows

@app.get("/api/done")
def done():
    c = connect()
    rows = _rows(c, "SELECT * FROM wishes WHERE status='fulfilled'"); c.close(); return rows

@app.get("/api/settings")
def settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close(); return rows

@app.get("/api/rules")
def rules():
    return {
        "mutex": "同一愿望同时只能被一人认领",
        "ttl": "认领超时未核销则自动释放",
        "fulfill": "核销后状态变为 fulfilled",
    }

# ---- 价位带：现行默认上限（源一：settings，可维护；只影响新发愿望）----

@app.get("/api/price-cap")
def price_cap_get():
    c = connect(); cap = get_default_cap(c); c.close()
    return {"cap": cap, "modes": list(BAND_MODES)}

class CapIn(BaseModel):
    cap: float

@app.put("/api/price-cap")
def price_cap_put(body: CapIn):
    if isinstance(body.cap, bool) or not math.isfinite(body.cap) or body.cap <= 0:
        raise HTTPException(400, ERR_INVALID_PRICE)
    c = connect(); set_default_cap(c, body.cap); c.commit(); c.close()
    return {"cap": body.cap}

# ---- 价位带：写入带（源二：每条愿望冻结的 band_snapshot，绝不回刷）----

@app.get("/api/price-cap/bands")
def price_cap_bands():
    """规则页「该愿望写入带」列表，只投影历史快照。"""
    c = connect(); sweep(c); c.commit()
    rows = _rows(c, "SELECT * FROM wishes ORDER BY id DESC")
    c.close()
    return [
        {"id": r["id"], "title": r["title"], "status": r["status"], "band": r["band"]}
        for r in rows if r["band"] is not None
    ]
