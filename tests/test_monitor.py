import asyncio, json
from datetime import datetime, timedelta, timezone
import pytest
from app.adapters.base import NormStream, normalize, AdapterError
from app.adapters.profiles import PROFILES
from app.db import DB
from app.monitor import Monitor, evaluate
from app import crypto


class FakeAdapter:
    profile = "v3"
    def __init__(self, streams): self.streams, self.restarted, self.fail = streams, [], False
    async def list_streams(self):
        if self.fail: raise AdapterError("Timeout")
        return self.streams
    async def get_stream_raw(self, n): return {"name": n, "stats": {"status": "error"}}
    async def restart(self, n): self.restarted.append(n); return {"http_status": 200}
    async def detect_version(self): return "23.01"
    async def close(self): pass


def ns(status="running", bitrate=2500, lag=0, name="ch1"):
    return NormStream(name, status, bitrate, lag, 100, True, {"name": name})


class Clock:
    def __init__(self): self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self): return self.t
    def adv(self, s): self.t += timedelta(seconds=s)


def setup(adapter):
    db = DB(":memory:")
    db.x("INSERT INTO servers(name,base_url,auto_restart) VALUES('h1','http://x',1)")
    clk = Clock()
    async def factory(s, t): return adapter
    return db, Monitor(db, None, factory, clk), clk


def run(c): return asyncio.run(c)


def test_evaluate():
    assert evaluate(ns(), 60) == []
    assert evaluate(ns("error", 0), 60)
    assert evaluate(ns(bitrate=None), 60) == ["bitrate zero/ausente"]
    assert evaluate(ns(lag=3600), 60)
    n = ns(bitrate=0); n.static = False
    assert evaluate(n, 60) == []  # sob demanda não conta


def test_normalize_v3():
    raw = {"name": "a", "stats": {"status": "running", "input_bitrate": 100, "lag_ms": 5000, "opened_at": 1700000000000}}
    n = normalize(raw, PROFILES["v3"], now=1700000100)
    assert (n.status, n.bitrate, n.lag_s, round(n.uptime_s)) == ("running", 100.0, 5.0, 100)


def test_persistence_then_restart_with_snapshot():
    a = FakeAdapter([ns("error", 0, 14400)])
    db, m, clk = setup(a)
    async def go():
        await m.poll_all(); await m.poll_all()
        assert a.restarted == []  # ainda < 3 verificações
        await m.poll_all()
    run(go())
    assert a.restarted == ["ch1"]
    snaps = db.q("SELECT * FROM snapshots")
    assert len(snaps) == 1 and json.loads(snaps[0]["raw"])["stats"]["status"] == "error"
    kinds = [e["kind"] for e in db.q("SELECT kind FROM events ORDER BY id")]
    assert "problem" in kinds and "auto_restart" in kinds


def test_min_interval_and_limit_critical():
    a = FakeAdapter([ns("error", 0, 14400)])
    db, m, clk = setup(a)
    db.set_settings({"persistence_checks": 1, "min_restart_interval_s": 300, "max_restarts_per_window": 2})
    async def go():
        await m.poll_all()                 # reinicio 1
        clk.adv(100); await m.poll_all()   # dentro do intervalo -> nada
        assert len(a.restarted) == 1
        clk.adv(300); await m.poll_all()   # reinicio 2
        clk.adv(300); await m.poll_all()   # limite -> critico
        clk.adv(300); await m.poll_all()   # suspenso
    run(go())
    assert len(a.restarted) == 2
    crit = db.q("SELECT * FROM events WHERE kind='restart_limit'")
    assert len(crit) == 1 and crit[0]["level"] == "critical"


def test_disabled_per_stream_and_server_offline():
    a = FakeAdapter([ns("error", 0, 14400)])
    db, m, clk = setup(a)
    db.set_settings({"persistence_checks": 1})
    async def go():
        await m.poll_all()
        a.restarted.clear()
        db.x("UPDATE streams SET auto_restart=0, last_restart_at=NULL")
        clk.adv(1000); await m.poll_all()
        assert a.restarted == []
        a.fail = True; await m.poll_all(); await m.poll_all()
    run(go())
    assert db.one("SELECT status FROM servers")["status"] == "offline"
    assert len(db.q("SELECT * FROM events WHERE kind='server_offline'")) == 1


def test_recovery_and_restart_ok():
    a = FakeAdapter([ns("error", 0, 14400)])
    db, m, clk = setup(a)
    db.set_settings({"persistence_checks": 1, "verify_after_s": 60})
    async def go():
        await m.poll_all()
        a.streams = [ns()]
        clk.adv(70); await m.poll_all()
    run(go())
    kinds = [e["kind"] for e in db.q("SELECT kind FROM events")]
    assert "restart_ok" in kinds and "recovered" in kinds


def test_credentials_encrypted(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path)); monkeypatch.setattr(crypto, "_fernet", None)
    monkeypatch.setattr(config, "SECRET_KEY", None)
    tok = crypto.encrypt_obj({"password": "segredo123"})
    assert "segredo123" not in tok and crypto.decrypt_obj(tok)["password"] == "segredo123"
