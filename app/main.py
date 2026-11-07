import asyncio, base64, json, logging, secrets
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .adapters.base import AdapterError, build_for_server
from .crypto import decrypt_obj, encrypt_obj
from .db import DB, iso, utcnow
from . import importer
from .monitor import Monitor
from .version import VERSAO
from .notify import CHANNEL_TYPES, Notifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # URLs/headers fora do log

db = DB()
notifier = Notifier(db)
monitor = Monitor(db, notifier)
security = HTTPBasic(auto_error=False)


def require_auth(cred: Optional[HTTPBasicCredentials] = Depends(security)):
    if not config.ADMIN_PASSWORD:
        return
    ok = cred and secrets.compare_digest(cred.username, config.ADMIN_USER) and \
        secrets.compare_digest(cred.password, config.ADMIN_PASSWORD)
    if not ok:
        raise HTTPException(401, "não autorizado", headers={"WWW-Authenticate": "Basic"})


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(monitor.run())
    yield
    monitor.stop()
    await task

app = FastAPI(title="Greentek Central de Monitoramento", version=VERSAO, lifespan=lifespan)


@app.middleware("http")
async def cabecalho_versao(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Greentek-Versao"] = VERSAO
    return resp
api = FastAPI(dependencies=[Depends(require_auth)])  # montado em /api; protegido se CENTRAL_ADMIN_PASSWORD definido


class ServerIn(BaseModel):
    name: str
    base_url: str
    auth_type: str = "basic"            # basic | bearer | none
    username: Optional[str] = None
    password: Optional[str] = None      # senha ou token (bearer); omitido na edição = manter
    verify_tls: bool = True
    adapter: str = "auto"               # auto | v3 | legacy
    tags: dict = {}
    enabled: bool = True
    auto_restart: bool = False


def public(s):
    s = dict(s)
    s.pop("credentials_enc", None)
    s["tags"] = json.loads(s["tags"] or "{}")
    return s


def _creds(body: ServerIn, old=None):
    cur = decrypt_obj(old["credentials_enc"]) if old and old.get("credentials_enc") else {}
    if body.auth_type == "bearer":
        if body.password:
            cur = {"token": body.password}
    elif body.auth_type == "basic":
        cur = {"username": body.username if body.username is not None else cur.get("username", ""),
               "password": body.password if body.password else cur.get("password", "")}
    else:
        cur = {}
    return encrypt_obj(cur)


def _validate(b: ServerIn):
    if not b.base_url.startswith(("http://", "https://")):
        raise HTTPException(422, "base_url deve começar com http:// ou https://")
    if b.auth_type not in ("basic", "bearer", "none") or b.adapter not in ("auto", "v3", "legacy"):
        raise HTTPException(422, "auth_type/adapter inválido")


def _server(sid):
    s = db.one("SELECT * FROM servers WHERE id=?", (sid,))
    if not s:
        raise HTTPException(404, "servidor não encontrado")
    return s


@api.get("/servers")
def list_servers():
    return [public(s) for s in db.q("SELECT * FROM servers ORDER BY name")]


class ImportIn(BaseModel):
    csv: str
    default_username: Optional[str] = None
    default_password: Optional[str] = None
    dry_run: bool = True             # True = só verifica; False = importa de fato


@api.get("/servers/import-modelo")
def import_modelo():
    return Response("\ufeff" + importer.MODELO, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="modelo-hoteis.csv"'})


@api.post("/servers/import")
def import_servers(b: ImportIn):
    rows, err = importer.parse(b.csv, b.default_username, b.default_password)
    if err:
        raise HTTPException(422, err)
    have_names = {r["name"].lower() for r in db.q("SELECT name FROM servers")}
    have_urls = {r["base_url"].lower() for r in db.q("SELECT base_url FROM servers")}
    linhas, imported = [], 0
    for r in rows:
        status, msg = "ok", ("será importado" if b.dry_run else "importado")
        if r["erro"]:
            status, msg = "erro", r["erro"]
        elif r["name"].lower() in have_names or r["base_url"].lower() in have_urls:
            status, msg = "duplicado", "já cadastrado (mesmo nome ou endereço); ignorado"
        elif not b.dry_run:
            body = ServerIn(name=r["name"], base_url=r["base_url"], username=r["username"], password=r["password"],
                            adapter=r["adapter"], auto_restart=r["auto_restart"],
                            tags={"cidade": r["cidade"]} if r["cidade"] else {})
            sid = db.x("INSERT INTO servers(name,base_url,auth_type,credentials_enc,verify_tls,adapter,tags,enabled,auto_restart,created_at)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (body.name, body.base_url, "basic", _creds(body), 1, body.adapter, json.dumps(body.tags), 1,
                        int(body.auto_restart), iso(utcnow())))
            db.add_event("info", "server_added", "Servidor cadastrado (importação)", _server(sid))
            imported += 1
        if status == "ok":
            have_names.add(r["name"].lower()); have_urls.add(r["base_url"].lower())
        linhas.append({"line": r["line"], "name": r["name"], "url": r["base_url"] or "", "status": status, "message": msg})
    cont = lambda s: sum(1 for x in linhas if x["status"] == s)
    return {"dry_run": b.dry_run, "total": len(linhas), "validos": cont("ok"), "duplicados": cont("duplicado"),
            "erros": cont("erro"), "importados": imported, "linhas": linhas}


@api.post("/servers", status_code=201)
def add_server(b: ServerIn):
    _validate(b)
    sid = db.x("INSERT INTO servers(name,base_url,auth_type,credentials_enc,verify_tls,adapter,tags,enabled,auto_restart,created_at)"
               " VALUES(?,?,?,?,?,?,?,?,?,?)",
               (b.name, b.base_url.rstrip("/"), b.auth_type, _creds(b), int(b.verify_tls), b.adapter, json.dumps(b.tags),
                int(b.enabled), int(b.auto_restart), iso(utcnow())))
    db.add_event("info", "server_added", "Servidor cadastrado", _server(sid))
    return public(_server(sid))


@api.put("/servers/{sid}")
def edit_server(sid: int, b: ServerIn):
    old = _server(sid)
    _validate(b)
    db.x("UPDATE servers SET name=?,base_url=?,auth_type=?,credentials_enc=?,verify_tls=?,adapter=?,tags=?,enabled=?,"
         "auto_restart=?,version=NULL WHERE id=?",
         (b.name, b.base_url.rstrip("/"), b.auth_type, _creds(b, old), int(b.verify_tls), b.adapter, json.dumps(b.tags),
          int(b.enabled), int(b.auto_restart), sid))
    return public(_server(sid))


@api.delete("/servers/{sid}", status_code=204)
def del_server(sid: int):
    s = _server(sid)
    db.x("DELETE FROM streams WHERE server_id=?", (sid,))
    db.x("DELETE FROM servers WHERE id=?", (sid,))
    db.add_event("info", "server_removed", "Servidor removido", s)
    return Response(status_code=204)


@api.post("/servers/{sid}/test")
async def test_server(sid: int):
    """Teste somente leitura: lista streams e detecta perfil/versão."""
    s = _server(sid)
    st = db.get_settings()
    creds = decrypt_obj(s["credentials_enc"]) if s["credentials_enc"] else {}
    try:
        a = await build_for_server(s, creds, st["request_timeout_s"])
        try:
            streams = await a.list_streams()
            return {"ok": True, "profile": a.profile, "streams": len(streams), "version": await a.detect_version()}
        finally:
            await a.close()
    except AdapterError as e:
        return {"ok": False, "error": str(e)}


@api.get("/overview")
def overview(server_id: Optional[int] = None, state: Optional[str] = None, only_problems: bool = False):
    out = []
    for s in db.q("SELECT * FROM servers ORDER BY name"):
        if server_id and s["id"] != server_id:
            continue
        rows = db.q("SELECT * FROM streams WHERE server_id=? AND present=1", (s["id"],))
        for r in rows:
            r["reasons"] = json.loads(r["reasons"])
            r.pop("raw", None)
            r["auto_restart_effective"] = bool(s["auto_restart"]) if r["auto_restart"] is None else bool(r["auto_restart"])
            r["problem_real"] = bool(r["problem"])             # o que a coleta viu
            r["problem"] = bool(r["problem"]) and not r["ignored"]  # o que conta como problema (ignorado não conta)
        rows.sort(key=lambda r: (not r["problem"], r["name"]))
        if state:
            rows = [r for r in rows if (r["status"] or "") == state]
        if only_problems:
            rows = [r for r in rows if r["problem"]]
        out.append({**public(s), "streams": rows})
    return out


class StreamRef(BaseModel):
    server_id: int
    name: str


class StreamSetting(StreamRef):
    auto_restart: Optional[bool] = None  # None = herdar do servidor


class StreamIgnore(StreamRef):
    ignored: bool
    note: Optional[str] = None


@api.put("/streams/ignore")
def stream_ignore(b: StreamIgnore):
    s = _server(b.server_id)
    if not db.one("SELECT 1 x FROM streams WHERE server_id=? AND name=?", (b.server_id, b.name)):
        raise HTTPException(404, "stream não encontrado")
    note = (b.note or "").strip()[:200] or None
    db.x("UPDATE streams SET ignored=?, ignore_note=?, ignored_at=? WHERE server_id=? AND name=?",
         (int(b.ignored), note if b.ignored else None, iso(utcnow()) if b.ignored else None, b.server_id, b.name))
    db.add_event("info", "stream_ignored" if b.ignored else "stream_unignored",
                 ("Stream ignorado" + (f": {note}" if note else "")) if b.ignored else "Stream voltou a ser monitorado",
                 s, b.name)
    return {"ok": True}


@api.post("/streams/restart")
async def manual_restart(b: StreamRef):
    s = _server(b.server_id)
    st = db.get_settings()
    try:
        a = await monitor.factory(s, st["request_timeout_s"])
    except AdapterError as e:
        raise HTTPException(502, str(e))
    try:
        ok = await monitor.restart_stream(s, b.name, a, ["solicitado pelo usuário"], auto=False)
    finally:
        await a.close()
    return {"ok": ok}


@api.put("/streams/settings")
def stream_setting(b: StreamSetting):
    _server(b.server_id)
    v = None if b.auto_restart is None else int(b.auto_restart)
    db.x("INSERT INTO streams(server_id,name,auto_restart) VALUES(?,?,?) ON CONFLICT(server_id,name) DO UPDATE SET auto_restart=excluded.auto_restart",
         (b.server_id, b.name, v))
    return {"ok": True}


@api.get("/events")
def events(server_id: Optional[int] = None, stream: Optional[str] = None, level: Optional[str] = None,
           kind: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None,
           limit: int = Query(200, le=1000), offset: int = 0):
    w, a = [], []
    for col, val, op in (("server_id", server_id, "="), ("stream", stream, "="), ("level", level, "="),
                         ("kind", kind, "="), ("ts", since, ">="), ("ts", until, "<=")):
        if val is not None:
            w.append(f"{col}{op}?"); a.append(val)
    sql = "SELECT * FROM events" + (" WHERE " + " AND ".join(w) if w else "") + " ORDER BY id DESC LIMIT ? OFFSET ?"
    return db.q(sql, (*a, limit, offset))


@api.get("/snapshots")
def snapshots(server_id: Optional[int] = None, stream: Optional[str] = None, limit: int = Query(100, le=500)):
    w, a = [], []
    if server_id: w.append("server_id=?"); a.append(server_id)
    if stream: w.append("stream=?"); a.append(stream)
    return db.q("SELECT id,ts,server_id,server_name,stream,stream_title,reason FROM snapshots" +
                (" WHERE " + " AND ".join(w) if w else "") + " ORDER BY id DESC LIMIT ?", (*a, limit))


@api.get("/snapshots/{snap_id}")
def snapshot(snap_id: int, download: bool = False):
    r = db.one("SELECT * FROM snapshots WHERE id=?", (snap_id,))
    if not r:
        raise HTTPException(404)
    r["raw"] = json.loads(r["raw"])
    headers = {"Content-Disposition": f'attachment; filename="snapshot-{snap_id}.json"'} if download else None
    return JSONResponse(r, headers=headers)


@api.get("/settings")
def get_settings():
    return db.get_settings()


@api.put("/settings")
def put_settings(values: dict):
    try:
        db.set_settings(values)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return db.get_settings()


class ChannelIn(BaseModel):
    type: str
    name: str
    config: dict = {}
    min_level: str = "warning"
    enabled: bool = True


@api.get("/channels")
def channels():
    return [{k: v for k, v in c.items() if k != "config_enc"} for c in db.q("SELECT * FROM channels")]


@api.post("/channels", status_code=201)
def add_channel(c: ChannelIn):
    if c.type not in CHANNEL_TYPES:
        raise HTTPException(422, f"tipo inválido; use {list(CHANNEL_TYPES)}")
    cid = db.x("INSERT INTO channels(type,name,config_enc,min_level,enabled) VALUES(?,?,?,?,?)",
               (c.type, c.name, encrypt_obj(c.config), c.min_level, int(c.enabled)))
    return {"id": cid}


class ChannelEdit(BaseModel):
    name: Optional[str] = None
    min_level: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[dict] = None   # mesclada com a atual: só os campos informados mudam (segredos não voltam do servidor)


@api.put("/channels/{cid}")
def edit_channel(cid: int, c: ChannelEdit):
    old = db.one("SELECT * FROM channels WHERE id=?", (cid,))
    if not old:
        raise HTTPException(404, "canal não encontrado")
    if c.min_level is not None and c.min_level not in ("info", "warning", "critical"):
        raise HTTPException(422, "min_level inválido")
    cfg = decrypt_obj(old["config_enc"]) if old["config_enc"] else {}
    if c.config:
        cfg = {**cfg, **c.config}
    db.x("UPDATE channels SET name=?,min_level=?,enabled=?,config_enc=? WHERE id=?",
         (c.name or old["name"], c.min_level or old["min_level"],
          int(c.enabled) if c.enabled is not None else old["enabled"], encrypt_obj(cfg), cid))
    return {k: v for k, v in db.one("SELECT * FROM channels WHERE id=?", (cid,)).items() if k != "config_enc"}


@api.delete("/channels/{cid}", status_code=204)
def del_channel(cid: int):
    db.x("DELETE FROM channels WHERE id=?", (cid,))
    return Response(status_code=204)


@api.post("/channels/{cid}/test")
async def test_channel(cid: int):
    ch = db.one("SELECT * FROM channels WHERE id=?", (cid,))
    if not ch:
        raise HTTPException(404)
    err = await notifier.send_one(ch, {"level": "info", "kind": "test", "message": "Teste de notificação",
                                       "server_name": None, "stream": None, "ts": iso(utcnow())})
    return {"ok": err is None, "error": err}


app.mount("/api", api)


@app.get("/health")
def health():
    return {"ok": True, "versao": VERSAO}


@app.get("/")
def index(_=Depends(require_auth)):
    html = open("static/index.html", encoding="utf-8").read().replace("{{VERSAO}}", VERSAO)
    return Response(html, media_type="text/html; charset=utf-8")
