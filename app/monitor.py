"""Coleta periódica, detecção de problema, alertas e reinício automático."""
import asyncio, json, logging, re
from datetime import timedelta
from . import db as dbm
from .adapters.base import AdapterError, build_for_server
from .crypto import decrypt_obj
from .notify import NOTIFY_ALSO

log = logging.getLogger("monitor")
ERROR_WORDS = ("error", "fail", "dead", "stopped")


def evaluate(ns, delay_threshold_s):
    """Retorna a lista de motivos pelos quais o stream é considerado com problema."""
    reasons = []
    if getattr(ns, "disabled", False):  # desativado de propósito no servidor: sem bitrate é esperado
        return reasons
    if ns.status and any(w in ns.status for w in ERROR_WORDS):
        reasons.append(f"status={ns.status}")
    elif ns.alive is False:
        reasons.append("alive=false")
    # Streams sob demanda (static=False) legitimamente ficam sem bitrate.
    if ns.static is not False and (ns.bitrate is None or ns.bitrate == 0):
        reasons.append("bitrate zero/ausente")
    if ns.lag_s is not None and ns.lag_s > delay_threshold_s:
        reasons.append(f"atraso {ns.lag_s:.0f}s > {delay_threshold_s}s")
    return reasons


class Monitor:
    def __init__(self, db, notifier=None, adapter_factory=None, clock=None):
        self.db, self.notifier = db, notifier
        self.factory = adapter_factory or self._default_factory
        self.now = clock or dbm.utcnow
        self._stop = asyncio.Event()

    async def _default_factory(self, server, timeout):
        creds = decrypt_obj(server["credentials_enc"]) if server.get("credentials_enc") else {}
        return await build_for_server(server, creds, timeout)

    # eventos ---------------------------------------------------------------
    async def emit(self, level, kind, message, server=None, stream=None, details=None):
        ev = self.db.add_event(level, kind, message, server, stream, details, now=self.now())
        if self.notifier and (level != "info" or kind in NOTIFY_ALSO):
            try:
                await self.notifier.enqueue(ev)
            except Exception:
                log.exception("erro ao despachar notificação")
        return ev

    # ciclo -----------------------------------------------------------------
    async def run(self):
        while not self._stop.is_set():
            st = self.db.get_settings()
            try:
                await self.poll_all(st)
                self.cleanup(st)
            except Exception:
                log.exception("falha no ciclo de coleta")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=max(1, st["poll_interval_s"]))
            except asyncio.TimeoutError:
                pass

    def stop(self):
        self._stop.set()

    def cleanup(self, st):
        now = self.now()
        self.db.x("DELETE FROM events WHERE ts < ?", (dbm.iso(now - timedelta(days=st["events_retention_days"])),))
        self.db.x("DELETE FROM snapshots WHERE ts < ?", (dbm.iso(now - timedelta(days=st["snapshots_retention_days"])),))

    async def poll_all(self, st=None):
        st = st or self.db.get_settings()
        servers = self.db.q("SELECT * FROM servers WHERE enabled=1")
        sem = asyncio.Semaphore(max(1, int(st["concurrency"])))

        async def one(s):
            async with sem:
                try:
                    await asyncio.wait_for(self.poll_server(s, st), timeout=st["request_timeout_s"] * 4 + 5)
                except Exception as e:  # um servidor nunca derruba os demais
                    await self._mark_offline(s, f"{type(e).__name__}: {str(e)[:150]}")
        n = self.notifier
        if n:
            n.batching = True   # os alertas do ciclo saem agrupados no fim, não um a um
        try:
            await asyncio.gather(*(one(s) for s in servers))
        finally:
            if n:
                n.batching = False
                try:
                    await n.flush()
                except Exception:
                    log.exception("erro ao enviar notificações do ciclo")

    async def _mark_offline(self, s, err):
        now = dbm.iso(self.now())
        prev = self.db.one("SELECT status FROM servers WHERE id=?", (s["id"],))["status"]
        self.db.x("UPDATE servers SET status='offline', last_error=?, last_poll=? WHERE id=?", (err, now, s["id"]))
        if prev != "offline":
            await self.emit("warning", "server_offline", f"Servidor inacessível: {err}", s)

    async def poll_server(self, s, st):
        adapter = None
        try:
            adapter = await self.factory(s, st["request_timeout_s"])
            streams = await adapter.list_streams()
        except AdapterError as e:
            await self._mark_offline(s, str(e))
            if adapter:
                await adapter.close()
            return
        try:
            now = self.now()
            nowi = dbm.iso(now)
            prev = self.db.one("SELECT status FROM servers WHERE id=?", (s["id"],))["status"]
            version = s.get("version")
            if not version:
                try:
                    version = await adapter.detect_version()
                except Exception:
                    version = None
            self.db.x("UPDATE servers SET status='online', last_error=NULL, last_seen=?, last_poll=?, adapter_used=?, "
                      "version=COALESCE(?,version) WHERE id=?", (nowi, nowi, adapter.profile, version, s["id"]))
            if prev == "offline":
                await self.emit("info", "server_online", "Servidor voltou a responder", s)
            seen = set()
            for ns in streams:
                seen.add(ns.name)
                await self.process_stream(s, ns, adapter, st)
            if seen:
                self.db.x("UPDATE streams SET present=0 WHERE server_id=? AND name NOT IN (%s)" % ",".join("?" * len(seen)),
                          (s["id"], *seen))
            else:
                self.db.x("UPDATE streams SET present=0 WHERE server_id=?", (s["id"],))
        finally:
            await adapter.close()

    # por stream ------------------------------------------------------------
    async def process_stream(self, s, ns, adapter, st):
        now = self.now()
        # grava o título primeiro, para que os eventos desta rodada já saiam com ele
        self.db.x("INSERT INTO streams(server_id,name,title) VALUES(?,?,?) "
                  "ON CONFLICT(server_id,name) DO UPDATE SET title=excluded.title", (s["id"], ns.name, ns.title))
        row = self.db.one("SELECT * FROM streams WHERE server_id=? AND name=?", (s["id"], ns.name)) or {}
        reasons = evaluate(ns, st["delay_threshold_s"])
        problem = bool(reasons)
        bad = (row.get("bad_count", 0) + 1) if problem else 0
        alerted, gave_up = row.get("alerted", 0), row.get("gave_up", 0)
        pending, last_restart = row.get("restart_pending", 0), row.get("last_restart_at")

        ignored = bool(row.get("ignored"))
        if ignored:
            # stream ignorado pelo usuário: continua sendo lido, mas não alerta, não reinicia e não conta como problema.
            # alerted=0 faz o alerta voltar na hora se a pessoa deixar de ignorar e o problema persistir.
            pending = alerted = gave_up = 0
        else:
            # verificação do resultado de um reinício anterior
            if pending and last_restart:
                if (now - dbm.parse_iso(last_restart)).total_seconds() >= st["verify_after_s"]:
                    if not problem:
                        await self.emit("info", "restart_ok", "Stream normalizado após reinício", s, ns.name)
                    else:
                        await self.emit("warning", "restart_failed", f"Stream continua com problema após reinício: {', '.join(reasons)}", s, ns.name)
                    pending = 0

            if not problem:
                if alerted and not ns.disabled:
                    await self.emit("info", "recovered", "Stream recuperado", s, ns.name)
                alerted = gave_up = 0
            elif bad >= st["persistence_checks"] and not alerted:
                alerted = 1
                await self.emit("warning", "problem", f"Problema persistente ({bad} verificações): {', '.join(reasons)}", s, ns.name,
                                {"reasons": reasons})

        self.db.x(
            "INSERT INTO streams(server_id,name,status,bitrate,lag_s,uptime_s,problem,reasons,bad_count,alerted,gave_up,"
            "last_restart_at,restart_pending,present,raw,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?) "
            "ON CONFLICT(server_id,name) DO UPDATE SET status=excluded.status,bitrate=excluded.bitrate,lag_s=excluded.lag_s,"
            "uptime_s=excluded.uptime_s,problem=excluded.problem,reasons=excluded.reasons,bad_count=excluded.bad_count,"
            "alerted=excluded.alerted,gave_up=excluded.gave_up,restart_pending=excluded.restart_pending,present=1,"
            "raw=excluded.raw,updated_at=excluded.updated_at",
            (s["id"], ns.name, ns.status, ns.bitrate, ns.lag_s, ns.uptime_s, int(problem), json.dumps(reasons), bad,
             alerted, gave_up, last_restart, pending, json.dumps(ns.raw), dbm.iso(now)))

        if problem and not ignored and bad >= st["persistence_checks"] and self.auto_enabled(s, row):
            await self.maybe_restart(s, ns, adapter, st, reasons, last_restart, gave_up)

    @staticmethod
    def auto_enabled(s, row):
        o = row.get("auto_restart")
        return bool(s["auto_restart"]) if o is None else bool(o)

    async def maybe_restart(self, s, ns, adapter, st, reasons, last_restart, gave_up):
        if gave_up:
            return
        now = self.now()
        if last_restart and (now - dbm.parse_iso(last_restart)).total_seconds() < st["min_restart_interval_s"]:
            return
        since = dbm.iso(now - timedelta(seconds=st["restart_window_s"]))
        n = self.db.one("SELECT COUNT(*) c FROM events WHERE server_id=? AND stream=? AND kind='auto_restart' AND ts>=?",
                        (s["id"], ns.name, since))["c"]
        if n >= st["max_restarts_per_window"]:
            self.db.x("UPDATE streams SET gave_up=1 WHERE server_id=? AND name=?", (s["id"], ns.name))
            await self.emit("critical", "restart_limit",
                            f"Limite de {n} reinícios na janela atingido; reinício automático suspenso para este stream",
                            s, ns.name, {"reasons": reasons})
            return
        await self.restart_stream(s, ns.name, adapter, reasons, auto=True, ns=ns)

    @staticmethod
    def redact(obj):
        """Mascara token/senha em URLs (ex.: ?token=..., user:senha@host) antes de gravar o snapshot."""
        if isinstance(obj, dict):
            return {k: ("***" if re.search(r"pass|secret|token", str(k), re.I) and isinstance(v, str) else Monitor.redact(v))
                    for k, v in obj.items()}
        if isinstance(obj, list):
            return [Monitor.redact(x) for x in obj]
        if isinstance(obj, str):
            obj = re.sub(r"(?i)((?:token|password|passwd|pass|key|secret)=)[^&\s\"']+", r"\1***", obj)
            return re.sub(r"(://[^/:@\s]+:)[^@/\s]+@", r"\1***@", obj)
        return obj

    async def restart_stream(self, s, name, adapter, reasons, auto, ns=None):
        """Salva o snapshot ANTES do reinício; o reinício é a única escrita e é sempre registrado."""
        raw = None
        try:
            raw = await adapter.get_stream_raw(name)
        except Exception as e:
            raw = {"_snapshot_error": f"{type(e).__name__}", "list_raw": ns.raw if ns else None}
        self.db.x("INSERT INTO snapshots(ts,server_id,server_name,stream,stream_title,reason,raw) VALUES(?,?,?,?,?,?,?)",
                  (dbm.iso(self.now()), s["id"], s["name"], name, self.db.stream_title(s["id"], name), ("auto: " if auto else "manual: ") + ", ".join(reasons or ["-"]),
                   json.dumps(self.redact(raw))))
        kind = "auto_restart" if auto else "manual_restart"
        try:
            res = await adapter.restart(name)
        except AdapterError as e:
            # Uma tentativa que falha também conta: respeita o intervalo mínimo e o limite por janela.
            self.db.x("UPDATE streams SET last_restart_at=? WHERE server_id=? AND name=?",
                      (dbm.iso(self.now()), s["id"], name))
            if auto:
                self.db.add_event("warning", "auto_restart", "Tentativa de reinício automático (falhou)",
                                  s, name, {"error": str(e)}, now=self.now())
            await self.emit("critical" if auto else "warning", "restart_error", f"Falha ao reiniciar: {e}", s, name)
            return False
        self.db.x("UPDATE streams SET last_restart_at=?, restart_pending=1 WHERE server_id=? AND name=?",
                  (dbm.iso(self.now()), s["id"], name))
        await self.emit("warning" if auto else "info", kind,
                        ("Reinício automático" if auto else "Reinício manual") + f" executado ({', '.join(reasons or [])})",
                        s, name, {"result": res})
        return True
