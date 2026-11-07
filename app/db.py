"""SQLite simples. Todos os horários em UTC (ISO 8601 com 'Z')."""
import json, sqlite3, threading, os
from datetime import datetime, timezone
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS servers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, base_url TEXT NOT NULL,
  auth_type TEXT NOT NULL DEFAULT 'basic', credentials_enc TEXT,
  verify_tls INTEGER NOT NULL DEFAULT 1, adapter TEXT NOT NULL DEFAULT 'auto',
  version TEXT, tags TEXT NOT NULL DEFAULT '{}', enabled INTEGER NOT NULL DEFAULT 1,
  auto_restart INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'unknown',
  last_error TEXT, last_seen TEXT, last_poll TEXT, adapter_used TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS streams(
  server_id INTEGER NOT NULL, name TEXT NOT NULL, status TEXT, bitrate REAL, lag_s REAL,
  uptime_s REAL, problem INTEGER NOT NULL DEFAULT 0, reasons TEXT NOT NULL DEFAULT '[]',
  bad_count INTEGER NOT NULL DEFAULT 0, alerted INTEGER NOT NULL DEFAULT 0,
  gave_up INTEGER NOT NULL DEFAULT 0, last_restart_at TEXT, restart_pending INTEGER NOT NULL DEFAULT 0,
  auto_restart INTEGER, present INTEGER NOT NULL DEFAULT 1, raw TEXT, updated_at TEXT,
  PRIMARY KEY(server_id,name));
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, server_id INTEGER, server_name TEXT,
  stream TEXT, level TEXT NOT NULL, kind TEXT NOT NULL, message TEXT, details TEXT);
CREATE INDEX IF NOT EXISTS ix_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS ix_events_srv ON events(server_id, stream);
CREATE TABLE IF NOT EXISTS snapshots(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, server_id INTEGER, server_name TEXT,
  stream TEXT, reason TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS channels(
  id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL, name TEXT NOT NULL,
  config_enc TEXT, min_level TEXT NOT NULL DEFAULT 'warning', enabled INTEGER NOT NULL DEFAULT 1);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if s else None


class DB:
    def __init__(self, path=None):
        path = path or config.DB_PATH
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            if path != ":memory:":
                self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.executescript(SCHEMA)
            # migração: colunas de título do stream (bancos criados antes da 0.3.0)
            for tbl, col in (("streams", "title"), ("events", "stream_title"), ("snapshots", "stream_title")):
                if col not in [r[1] for r in self.conn.execute(f"PRAGMA table_info({tbl})")]:
                    self.conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} TEXT")
            self.conn.commit()

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def x(self, sql, args=()):
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    # settings -----------------------------------------------------------
    def get_settings(self):
        out = dict(config.DEFAULT_SETTINGS)
        for r in self.q("SELECT key,value FROM settings"):
            if r["key"] in out:
                out[r["key"]] = json.loads(r["value"])
        return out

    def set_settings(self, values: dict):
        for k, v in values.items():
            if k in config.DEFAULT_SETTINGS:
                if not isinstance(v, (int, float)) or v < 0:
                    raise ValueError(f"valor inválido para {k}")
                self.x("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (k, json.dumps(v)))

    # events -------------------------------------------------------------
    def add_event(self, level, kind, message, server=None, stream=None, details=None, now=None):
        ts = iso(now or utcnow())
        title = self.stream_title(server["id"], stream) if server and stream else None
        eid = self.x(
            "INSERT INTO events(ts,server_id,server_name,stream,stream_title,level,kind,message,details) VALUES(?,?,?,?,?,?,?,?,?)",
            (ts, server["id"] if server else None, server["name"] if server else None, stream, title,
             level, kind, message, json.dumps(details) if details is not None else None))
        return {"id": eid, "ts": ts, "level": level, "kind": kind, "message": message,
                "server_name": server["name"] if server else None, "stream": stream, "stream_title": title}

    def stream_title(self, server_id, stream):
        r = self.one("SELECT title FROM streams WHERE server_id=? AND name=?", (server_id, stream))
        return (r or {}).get("title")
