"""SQLite persistence with write-behind batching, plus the hash-chained audit ledger.

Events, alerts and audit records are queued in memory and flushed in one transaction (executemany) by a background task,
instead of one commit per event. The audit hash chain is computed in memory in append order, so batching never reorders it."""
import hashlib, json, os, sqlite3, threading, time

DB = os.environ.get("TETHER_DB", os.path.join(os.path.dirname(__file__), "..", "..", "data", "tether.db"))
_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
GENESIS = "0" * 64
_q_events: list = []
_q_alerts: dict = {}
_q_audit: list = []
_head = GENESIS
_count = 0
stats = dict(flushes=0, rows=0, last_flush_ms=0.0)


def init(fresh: bool = True):
    global _conn, _head, _count
    with _lock:
        if _conn:
            _conn.close()
        if fresh:
            for ext in ("", "-wal", "-shm"):
                if os.path.exists(DB + ext): os.remove(DB + ext)
        _conn = sqlite3.connect(DB, check_same_thread=False, isolation_level=None)
        _conn.execute("PRAGMA journal_mode=WAL"); _conn.execute("PRAGMA synchronous=OFF"); _conn.execute("PRAGMA temp_store=MEMORY")
        _conn.executescript("""
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, ts REAL, agent TEXT, tool TEXT, risk REAL, verdict TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, ts REAL, agent TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS audit(idx INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, prev TEXT, hash TEXT, payload TEXT);
        CREATE INDEX IF NOT EXISTS ev_agent ON events(agent, id);
        """)
        _q_events.clear(); _q_alerts.clear(); _q_audit.clear(); _head = GENESIS; _count = 0


def save_event(out: dict):
    _q_events.append(out)


def save_alert(al: dict):
    _q_alerts[al["id"]] = al


def pending() -> int:
    return len(_q_events) + len(_q_alerts) + len(_q_audit)


def flush():
    """Write everything queued in a single transaction. Safe to call from any thread."""
    global stats
    with _lock:
        if not (_q_events or _q_alerts or _q_audit): return 0
        t0 = time.perf_counter()
        ev = [(o["event"]["id"], o["event"]["ts"], o["event"]["agent"], o["event"]["tool"], o["risk"], o["verdict"], json.dumps(o, default=str)) for o in _q_events]
        al = [(a["id"], a["opened"], a["agent"], json.dumps(a, default=str)) for a in _q_alerts.values()]
        au = list(_q_audit)
        _q_events.clear(); _q_alerts.clear(); _q_audit.clear()
        _conn.execute("BEGIN")
        if ev: _conn.executemany("INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?)", ev)
        if al: _conn.executemany("INSERT OR REPLACE INTO alerts VALUES(?,?,?,?)", al)
        if au: _conn.executemany("INSERT INTO audit(ts,prev,hash,payload) VALUES(?,?,?,?)", au)
        _conn.execute("COMMIT")
        n = len(ev) + len(al) + len(au)
        stats = dict(flushes=stats["flushes"] + 1, rows=stats["rows"] + n, last_flush_ms=round((time.perf_counter() - t0) * 1000, 2))
        return n


def get_event(eid: int):
    flush()
    with _lock:
        r = _conn.execute("SELECT body FROM events WHERE id=?", (eid,)).fetchone()
    return json.loads(r[0]) if r else None


def recent_events(limit=100, agent=None, flagged=False):
    flush()
    q, args, cond = "SELECT body FROM events", [], []
    if agent: cond.append("agent=?"); args.append(agent)
    if flagged: cond.append("risk>=50")
    if cond: q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY id DESC LIMIT ?"; args.append(limit)
    with _lock:
        rows = _conn.execute(q, args).fetchall()
    return [json.loads(r[0]) for r in rows]


# ---------------------------------------------------------------- audit ledger
def _h(prev: str, payload: str) -> str:
    return hashlib.sha256((prev + payload).encode()).hexdigest()


def audit_append(record: dict) -> dict:
    global _head, _count
    payload = json.dumps(record, sort_keys=True, default=str)
    with _lock:
        prev = _head; h = _h(prev, payload); _head = h; _count += 1
        _q_audit.append((time.time(), prev, h, payload))
        return dict(idx=_count, hash=h, prev=prev)


def audit_list(limit=40):
    flush()
    with _lock:
        rows = _conn.execute("SELECT idx,ts,prev,hash,payload FROM audit ORDER BY idx DESC LIMIT ?", (limit,)).fetchall()
    return [dict(idx=r[0], ts=r[1], prev=r[2], hash=r[3], payload=json.loads(r[4])) for r in rows]


def audit_verify() -> dict:
    flush()
    with _lock:
        rows = _conn.execute("SELECT idx,prev,hash,payload FROM audit ORDER BY idx").fetchall()
    prev, broken = GENESIS, None
    for idx, p, h, payload in rows:
        if p != prev or _h(p, payload) != h:
            broken = idx; break
        prev = h
    return dict(ok=broken is None, records=len(rows), first_broken=broken, head=prev)


def audit_tamper() -> dict:
    """Demo: silently alter one old record to show the ledger detects it."""
    flush()
    with _lock:
        row = _conn.execute("SELECT idx,payload FROM audit ORDER BY idx LIMIT 1 OFFSET 8").fetchone()
        if not row:
            return dict(ok=False, reason="not enough records yet")
        d = json.loads(row[1]); d["verdict"] = "ALLOW"; d["tampered"] = True
        _conn.execute("UPDATE audit SET payload=? WHERE idx=?", (json.dumps(d, sort_keys=True), row[0]))
    return dict(ok=True, idx=row[0])


def audit_rebuild() -> dict:
    """Re-seal the chain after an investigation (keeps payloads, recomputes hashes)."""
    global _head
    flush()
    with _lock:
        rows = _conn.execute("SELECT idx,payload FROM audit ORDER BY idx").fetchall()
        prev = GENESIS
        _conn.execute("BEGIN")
        for idx, payload in rows:
            h = _h(prev, payload); _conn.execute("UPDATE audit SET prev=?,hash=? WHERE idx=?", (prev, h, idx)); prev = h
        _conn.execute("COMMIT")
        _head = prev
    return dict(ok=True, records=len(rows))
