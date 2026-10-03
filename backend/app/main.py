from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.engines.claim_lock import claim_allowed, lock_payload, release_if_expired
from app.modules import price_cap as pc
from app.modules.price_cap import project_wish

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

@app.get("/api/health")
def health(): return {"ok": True, "project": "wishclaim"}

@app.get("/api/wishes")
def list_wishes():
    c = connect(); sweep(c); c.commit()
    rows = [project_wish(dict(r)) for r in c.execute("SELECT * FROM wishes ORDER BY id DESC")]; c.close(); return rows

@app.get("/api/wishes/{wid}")
def get_wish(wid: int):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone(); c.close()
    if not r: raise HTTPException(404, "not found")
    return project_wish(dict(r))

class WishIn(BaseModel):
    title: str
    note: str = ""
    estimate: Optional[float] = None
    band_mode: Optional[Literal["soft", "hard"]] = None

@app.post("/api/wishes")
def create_wish(body: WishIn):
    # 1. dirty-wish gate: blank title is never written.
    try:
        title = pc.validate_title(body.title)
    except ValueError as e:
        raise HTTPException(422, str(e))
    # 2. estimate / band_mode validation. estimate omitted -> legacy shape.
    try:
        estimate = pc.validate_estimate(body.estimate)
        band_mode = pc.validate_band_mode(body.band_mode, estimate is not None)
    except ValueError as e:
        raise HTTPException(422, str(e))

    c = connect()
    cap = pc.default_cap(c)

    snapshot = None
    warning = None
    if estimate is not None:
        verdict = pc.judge(estimate, band_mode, cap)
        if verdict["blocked"]:
            # hard gate: whole order fails, wishes table gains no row.
            c.close()
            raise HTTPException(422, pc.BLOCK_OVER_HARD_CAP)
        snapshot = pc.build_snapshot(estimate, band_mode, cap, verdict, now().isoformat())
        warning = verdict["warning"]

    cur = c.execute(
        "INSERT INTO wishes(title,note,status,data_quality,estimate,band_mode,band_json) "
        "VALUES (?,?,?,?,?,?,?)",
        (title, body.note, "open", "clean", estimate, band_mode,
         pc.dumps_snapshot(snapshot) if snapshot else None),
    )
    c.commit(); wid = cur.lastrowid; c.close()
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
    rows = [project_wish(dict(r)) for r in c.execute("SELECT * FROM wishes WHERE claimer=?", (claimer,))]; c.close(); return rows

@app.get("/api/done")
def done():
    c = connect()
    rows = [project_wish(dict(r)) for r in c.execute("SELECT * FROM wishes WHERE status='fulfilled'")]; c.close(); return rows

@app.get("/api/settings")
def settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close(); return rows

class CapIn(BaseModel):
    cap: float

@app.put("/api/settings/price_cap")
def update_price_cap(body: CapIn):
    """Maintain the current default cap. Applies to new wishes only."""
    try:
        value = pc.validate_estimate(body.cap)  # reuse the positive-number rule
    except ValueError as e:
        raise HTTPException(422, str(e))
    c = connect(); pc.set_default_cap(c, value); c.commit(); c.close()
    return {"ok": True, "default_cap": value}

@app.get("/api/rules")
def rules():
    c = connect()
    cap = pc.default_cap(c)
    # Second source: per-wish snapshots written at creation time, never recomputed.
    written = [
        {"id": w["id"], "title": w["title"], "band": w["band"]}
        for w in pc.written_band_rows(c)
    ]
    c.close()
    return {
        "rules": {
            "mutex": "同一愿望同时只能被一人认领",
            "ttl": "认领超时未核销则自动释放",
            "fulfill": "核销后状态变为 fulfilled",
        },
        "price_cap": {
            "default_cap": cap,
            "default_source": pc.SETTINGS_KEY,
            "warning_code": pc.WARN_OVER_SOFT_CAP,
            "written": written,
        },
    }
