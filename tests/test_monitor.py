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
    raw = {"name": "a", "stats": {"status": "running", "bitrate": 100, "ts_delay": 5000, "opened_at": 1700000000000}}
    n = normalize(raw, PROFILES["v3"], now=1700000100)
    assert (n.status, n.bitrate, n.lag_s, round(n.uptime_s)) == ("running", 100.0, 5.0, 100)


def test_normalize_manual_example():
    # exemplo literal do manual (GET /streamer/api/v3/streams/ort), sem stats.status
    raw = {"effective": {"name": "ort", "static": True}, "name": "ort", "static": True,
           "stats": {"alive": False, "opened_at": 1632202350648, "retry_count": 19, "running": True}}
    n = normalize(raw, PROFILES["v3"], now=1632202450.648)
    assert (n.status, n.alive, n.static, n.bitrate, round(n.uptime_s)) == ("error", False, True, None, 100)
    assert evaluate(n, 60)
    n2 = normalize({"name": "a", "stats": {"alive": True, "bitrate": 3000, "ts_delay": 14400000}}, PROFILES["v3"])
    assert n2.lag_s == 14400 and evaluate(n2, 60) == ["atraso 14400s > 60s"]


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


def test_restart_tries_candidates_per_version():
    import asyncio, httpx
    from app.adapters import base

    def make(ok_method, ok_path, base_url):
        def handler(req):
            if req.method == ok_method and req.url.path == ok_path:
                return httpx.Response(200, text="true")
            return httpx.Response(404, text="Not found")
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return base.Adapter(base_url, "none", {}, 5, True, "v3", client)

    old = make("GET", "/flussonic/api/stream_restart/25", "http://old")
    new = make("POST", "/streamer/api/v3/streams/25/restart", "http://new")
    none = make("POST", "/nada", "http://none")
    r1 = asyncio.run(old.restart("25"))
    r2 = asyncio.run(new.restart("25"))
    assert r1["endpoint"].startswith("GET /flussonic/api/stream_restart")
    assert r2["endpoint"].startswith("POST /streamer/api/v3/streams")
    assert base._RESTART_OK[("http://new", "v3")][0] == "POST"  # lembrou
    try:
        asyncio.run(none.restart("25"))
        assert False
    except base.AdapterError as e:
        assert "nenhum endereço de reinício" in str(e)


def test_versao_visivel_em_header_health_e_rodape(tmp_path, monkeypatch):
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CENTRAL_ADMIN_PASSWORD", raising=False)
    from fastapi.testclient import TestClient
    from app.version import VERSAO
    import app.main as m
    with TestClient(m.app) as c:
        for path in ("/health", "/"):
            r = c.get(path)
            assert r.headers["X-Greentek-Versao"] == VERSAO
        assert c.get("/health").json()["versao"] == VERSAO
        assert "{{VERSAO}}" not in c.get("/").text


def test_telegram_erro_mostra_motivo_sem_vazar_token(monkeypatch):
    import asyncio, httpx
    from app import notify
    TOKEN = "123456:SEGREDO"

    def handler(req):
        return httpx.Response(403, json={"ok": False, "description": "Forbidden: bot is not a member of the channel chat"})
    real = httpx.AsyncClient
    monkeypatch.setattr(notify.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    ch = {"name": "t", "type": "telegram", "config_enc": "x"}
    monkeypatch.setattr("app.crypto.decrypt_obj", lambda _: {"bot_token": TOKEN, "chat_id": "@canal"})
    err = asyncio.run(notify.Notifier(None).send_one(ch, {"level": "info", "kind": "test", "message": "m",
                                                           "server_name": None, "stream": None, "ts": "2026-01-01T00:00:00Z"}))
    assert "not a member" in err and "SEGREDO" not in err and "403" in err


def test_eventos_e_evidencias_levam_o_titulo_do_stream():
    n = ns("error", 0, 14400, name="25"); n.title = "SporTV 2 HD"
    a = FakeAdapter([n])
    db, m, clk = setup(a)
    async def go():
        for _ in range(3):
            await m.poll_all()
    run(go())
    evs = db.q("SELECT kind,stream,stream_title FROM events WHERE stream='25'")
    assert evs and all(e["stream_title"] == "SporTV 2 HD" for e in evs)
    assert db.q("SELECT stream_title FROM snapshots")[0]["stream_title"] == "SporTV 2 HD"


def test_normalize_le_title_e_banco_antigo_e_migrado(tmp_path):
    assert normalize({"name": "25", "title": "  SporTV 2  "}, PROFILES["v3"]).title == "SporTV 2"
    assert normalize({"name": "25"}, PROFILES["v3"]).title is None
    import sqlite3
    f = str(tmp_path / "old.db")
    c = sqlite3.connect(f)
    c.executescript("CREATE TABLE events(id INTEGER PRIMARY KEY, ts TEXT, server_id INTEGER, server_name TEXT, stream TEXT,"
                    " level TEXT, kind TEXT, message TEXT, details TEXT);")
    c.commit(); c.close()
    d = DB(f)  # não pode falhar nem perder a tabela antiga
    assert "stream_title" in [r["name"] for r in d.q("PRAGMA table_info(events)")]


def test_notificacao_mostra_titulo():
    from app.notify import _text
    t = _text({"level": "warning", "server_name": "h1", "stream": "25", "stream_title": "SporTV 2", "message": "x", "ts": "t"})
    assert "25 (SporTV 2)" in t


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("CENTRAL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CENTRAL_ADMIN_PASSWORD", raising=False)
    from fastapi.testclient import TestClient
    import app.main as m
    return TestClient(m.app), m


def test_editar_servidor_mantem_senha_quando_omitida(tmp_path, monkeypatch):
    c, m = _client(tmp_path, monkeypatch)
    with c:
        sid = c.post("/api/servers", json={"name": "h", "base_url": "http://x:1", "username": "u", "password": "segredo"}).json()["id"]
        r = c.put(f"/api/servers/{sid}", json={"name": "h2", "base_url": "http://y:2", "auth_type": "basic"})
        assert r.status_code == 200 and r.json()["name"] == "h2" and r.json()["base_url"] == "http://y:2"
        cred = crypto.decrypt_obj(m.db.one("SELECT credentials_enc FROM servers WHERE id=?", (sid,))["credentials_enc"])
        assert cred == {"username": "u", "password": "segredo"}


def test_editar_canal_mescla_config_sem_expor_segredo(tmp_path, monkeypatch):
    c, m = _client(tmp_path, monkeypatch)
    with c:
        cid = c.post("/api/channels", json={"type": "telegram", "name": "t", "config": {"bot_token": "TOK", "chat_id": "@a"}}).json()["id"]
        r = c.put(f"/api/channels/{cid}", json={"name": "t2", "enabled": False, "config": {"chat_id": "@b"}})
        assert r.status_code == 200 and r.json()["name"] == "t2" and r.json()["enabled"] == 0 and "config_enc" not in r.json()
        cfg = crypto.decrypt_obj(m.db.one("SELECT config_enc FROM channels WHERE id=?", (cid,))["config_enc"])
        assert cfg == {"bot_token": "TOK", "chat_id": "@b"}
        assert c.put(f"/api/channels/{cid}", json={"min_level": "xx"}).status_code == 422
        assert c.put("/api/channels/999", json={}).status_code == 404


def test_importador_formatos_do_excel_e_erros():
    from app import importer
    txt = ("﻿Hotel;URL;Usuário;Senha;Cidade\n"
           "Hotel A;hotel-a.exemplo.com:7777;;;São Paulo\n"
           "# comentário\n\n"
           "Hotel B;http://hotel-b.exemplo.com:7777;proprio;segredo;Santos\n"
           ";http://x:1;;;\n"
           "Hotel D;ftp://x;;;\n")
    rows, err = importer.parse(txt, "padrao", "senhapadrao")
    assert err is None and len(rows) == 4
    a, b, c, d = rows
    assert a["erro"] is None and a["base_url"] == "http://hotel-a.exemplo.com:7777" and a["username"] == "padrao" and a["cidade"] == "São Paulo"
    assert b["username"] == "proprio" and b["password"] == "segredo"  # a linha vale mais que o padrão
    assert c["erro"] == "nome em branco" and "url inválida" in d["erro"]
    rows, _ = importer.parse("nome,url\nH,http://h:1\n")  # vírgula, sem credenciais
    assert "sem usuário/senha" in rows[0]["erro"]
    assert importer.parse("foo;bar\n1;2\n")[1] and importer.parse("")[1]


def test_importar_via_api_verifica_importa_e_ignora_duplicados(tmp_path, monkeypatch):
    c, m = _client(tmp_path, monkeypatch)
    csvtxt = "nome;url;cidade\nHotel A;http://a:1;SP\nHotel B;http://b:1;RJ\nHotel A;http://outro:1;SP\nHotel C;http://c:1;\n;http://d:1;\n"
    body = {"csv": csvtxt, "default_username": "u", "default_password": "SENHA-SECRETA"}
    with c:
        m.db.x("DELETE FROM servers")  # o banco do app é compartilhado entre os testes
        r = c.post("/api/servers/import", json=body).json()          # só verifica
        assert (r["dry_run"], r["total"], r["validos"], r["duplicados"], r["erros"], r["importados"]) == (True, 5, 3, 1, 1, 0)
        assert c.get("/api/servers").json() == []
        r = c.post("/api/servers/import", json={**body, "dry_run": False}).json()
        assert r["importados"] == 3 and "SENHA-SECRETA" not in str(r)  # senha nunca volta na resposta
        servers = c.get("/api/servers").json()
        assert [s["name"] for s in servers] == ["Hotel A", "Hotel B", "Hotel C"] and servers[0]["tags"] == {"cidade": "SP"}
        cred = crypto.decrypt_obj(m.db.one("SELECT credentials_enc FROM servers WHERE name='Hotel A'")["credentials_enc"])
        assert cred == {"username": "u", "password": "SENHA-SECRETA"}
        r = c.post("/api/servers/import", json={**body, "dry_run": False}).json()  # reimportar não duplica
        assert r["importados"] == 0 and r["duplicados"] == 4
        assert c.post("/api/servers/import", json={"csv": "x;y\n1;2"}).status_code == 422
        assert "nome;url" in c.get("/api/servers/import-modelo").text


def test_stream_ignorado_nao_alerta_nao_reinicia_e_volta_a_alertar_ao_deixar_de_ignorar():
    a = FakeAdapter([ns("error", 0, 14400, name="25")])
    db, m, clk = setup(a)
    async def go():
        await m.poll_all()                      # cria o registro do stream
        db.x("UPDATE streams SET ignored=1, ignore_note='fonte fora do ar'")
        for _ in range(6):
            clk.adv(31); await m.poll_all()
    run(go())
    assert a.restarted == []
    assert db.q("SELECT 1 FROM events WHERE kind IN ('problem','auto_restart','restart_limit')") == []
    assert db.one("SELECT problem FROM streams")["problem"] == 1     # continua sendo lido (a realidade fica visível)
    db.x("UPDATE streams SET ignored=0")
    run(m.poll_all())                                                 # persistência já cumprida: alerta e reinício voltam
    assert db.q("SELECT 1 FROM events WHERE kind='problem'") and a.restarted == ["25"]


def test_api_ignorar_stream_tira_da_contagem_de_problemas_e_registra_evento(tmp_path, monkeypatch):
    c, m = _client(tmp_path, monkeypatch)
    with c:
        m.db.x("DELETE FROM servers"); m.db.x("DELETE FROM streams")
        sid = m.db.x("INSERT INTO servers(name,base_url) VALUES('h','http://x')")
        m.db.x("INSERT INTO streams(server_id,name,problem,reasons,present) VALUES(?,'25',1,'[\"x\"]',1)", (sid,))
        m.db.x("INSERT INTO streams(server_id,name,problem,reasons,present) VALUES(?,'26',1,'[\"x\"]',1)", (sid,))
        assert [x["problem"] for x in c.get("/api/overview").json()[0]["streams"]] == [True, True]
        assert c.put("/api/streams/ignore", json={"server_id": sid, "name": "25", "ignored": True, "note": "  fonte fora  "}).status_code == 200
        st = {x["name"]: x for x in c.get("/api/overview").json()[0]["streams"]}
        assert st["25"]["ignored"] == 1 and st["25"]["problem"] is False and st["25"]["problem_real"] is True
        assert st["25"]["ignore_note"] == "fonte fora" and st["26"]["problem"] is True
        assert [x["name"] for x in c.get("/api/overview?only_problems=true").json()[0]["streams"]] == ["26"]
        assert c.get("/api/overview").json()[0]["streams"][0]["name"] == "26"   # ignorado vai para o fim
        ev = m.db.q("SELECT kind,level,stream FROM events WHERE kind='stream_ignored'")
        assert ev == [{"kind": "stream_ignored", "level": "info", "stream": "25"}]
        c.put("/api/streams/ignore", json={"server_id": sid, "name": "25", "ignored": False})
        assert m.db.one("SELECT ignored,ignore_note FROM streams WHERE name='25'") == {"ignored": 0, "ignore_note": None}
        assert c.put("/api/streams/ignore", json={"server_id": sid, "name": "zzz", "ignored": True}).status_code == 404


def test_testes_nunca_usam_o_banco_de_verdade():
    from app import config
    assert "central-testes-" in config.DB_PATH and "central-testes-" in config.DATA_DIR


def test_falha_de_notificacao_vira_evento_visivel(monkeypatch):
    import asyncio
    from app import notify
    from app.db import DB
    import app.main as m

    async def falha(self, ch, ev):
        return "Telegram recusou (HTTP 429): Too Many Requests"
    monkeypatch.setattr(notify.Notifier, "send_one", falha)

    async def sem_espera(_):
        return None
    monkeypatch.setattr(notify.asyncio, "sleep", sem_espera)
    db = m.db
    db.x("DELETE FROM channels"); db.x("DELETE FROM events")
    db.x("INSERT INTO channels(type,name,config_enc,min_level,enabled) VALUES('telegram','tg','x','warning',1)")
    ev = {"level": "warning", "kind": "problem", "message": "m", "server_name": "h", "stream": "1", "ts": "t"}
    asyncio.run(notify.Notifier(db).dispatch(ev))
    e = db.q("SELECT * FROM events WHERE kind='notify_error'")
    assert len(e) == 1 and "429" in e[0]["message"] and "tg" in e[0]["message"]


def test_notificacoes_agrupadas_e_recuperacao(monkeypatch):
    import asyncio
    from app import notify
    enviados = []

    async def envia(self, ch, ev):
        enviados.append(ev)
        return None
    monkeypatch.setattr(notify.Notifier, "send_one", envia)
    import app.main as m
    db = m.db
    db.x("DELETE FROM channels"); db.x("DELETE FROM events")
    db.x("INSERT INTO channels(type,name,config_enc,min_level,enabled) VALUES('telegram','tg','x','warning',1)")
    n = notify.Notifier(db)

    def ev(h, kind="problem", lv="warning"):
        return {"level": lv, "kind": kind, "message": "m", "server_name": f"Hotel {h}", "stream": "7",
                "stream_title": "CNN", "ts": "t"}
    n.batching = True
    for h in range(20):
        asyncio.run(n.enqueue(ev(h)))
    assert enviados == []                      # nada sai durante o ciclo
    asyncio.run(n.flush())
    assert len(enviados) == 1                  # 20 alertas viram 1 mensagem
    assert "20" in enviados[0]["message"] and "CNN" in enviados[0]["message"]
    enviados.clear()
    for h in range(2):
        asyncio.run(n.enqueue(ev(h)))
    asyncio.run(n.flush())
    assert len(enviados) == 2                  # poucos eventos saem individuais
    enviados.clear()
    n.batching = False
    asyncio.run(n.enqueue(ev(1, "recovered", "info")))
    assert len(enviados) == 1                  # recuperação é avisada mesmo sendo info


def test_ssh_padrao_servidor_sobrescreve_e_senha_nunca_vaza(tmp_path, monkeypatch):
    c, m = _client(tmp_path, monkeypatch)
    chamadas = []

    async def falso(host, port, user, pw, cmd, timeout=20):
        chamadas.append((host, port, user, pw, cmd))
        return 0
    monkeypatch.setattr(m.sshm, "run", falso)
    with c:
        m.db.x("DELETE FROM servers"); m.db.x("DELETE FROM settings WHERE key LIKE 'ssh_default_%'")
        s1 = c.post("/api/servers", json={"name": "a", "base_url": "http://10.0.0.1:8080", "username": "u", "password": "p"}).json()
        assert s1["ssh_efetivo"] is False
        r = c.post(f"/api/servers/{s1['id']}/ssh/reboot")
        assert r.status_code == 422                                  # sem SSH configurado
        d = c.put("/api/ssh-padrao", json={"port": 2222, "user": "root", "password": "SEGREDO_PADRAO"}).json()
        assert d == {"port": 2222, "user": "root", "has_password": True}
        assert c.post(f"/api/servers/{s1['id']}/ssh/restart-service").json() == {"ok": True}
        assert chamadas[-1][:4] == ("10.0.0.1", 2222, "root", "SEGREDO_PADRAO") and "systemctl restart flussonic" in chamadas[-1][4]
        # servidor com SSH próprio sobrescreve usuário, senha e porta
        s2 = c.post("/api/servers", json={"name": "b", "base_url": "https://h2.exemplo.com", "username": "u", "password": "p",
                                          "ssh_port": 2200, "ssh_user": "admin", "ssh_password": "SEGREDO_PROPRIO"}).json()
        c.post(f"/api/servers/{s2['id']}/ssh/reboot")
        assert chamadas[-1][:4] == ("h2.exemplo.com", 2200, "admin", "SEGREDO_PROPRIO") and "reboot" in chamadas[-1][4]
        # usuário próprio sem senha é recusado
        assert c.post("/api/servers", json={"name": "c", "base_url": "http://x:1", "username": "u", "password": "p",
                                            "ssh_user": "so_usuario"}).status_code == 422
        # nada de senha nas respostas, no banco em texto puro ou nos eventos
        corpo = c.get("/api/servers").text + c.get("/api/overview").text + c.get("/api/ssh-padrao").text + c.get("/api/events").text
        assert "SEGREDO" not in corpo
        bruto = str(m.db.q("SELECT * FROM servers")) + str(m.db.q("SELECT * FROM settings"))
        assert "SEGREDO" not in bruto
        # editar sem mandar os campos SSH mantém tudo; ssh_user "" volta ao padrão
        c.put(f"/api/servers/{s2['id']}", json={"name": "b2", "base_url": "https://h2.exemplo.com", "auth_type": "basic"})
        c.post(f"/api/servers/{s2['id']}/ssh/reboot")
        assert chamadas[-1][2] == "admin"
        c.put(f"/api/servers/{s2['id']}", json={"name": "b2", "base_url": "https://h2.exemplo.com", "auth_type": "basic", "ssh_user": ""})
        c.post(f"/api/servers/{s2['id']}/ssh/reboot")
        assert chamadas[-1][2] == "root"
        assert {"ssh_reboot", "ssh_restart_service"} <= {e["kind"] for e in m.db.q("SELECT kind FROM events")}


def test_ssh_falha_vira_evento_sem_senha(tmp_path, monkeypatch):
    c, m = _client(tmp_path, monkeypatch)

    async def quebra(*a, **k):
        raise m.sshm.SSHError("autenticação SSH recusada (usuário ou senha)")
    monkeypatch.setattr(m.sshm, "run", quebra)
    with c:
        sid = c.post("/api/servers", json={"name": "d", "base_url": "http://x:1", "username": "u", "password": "p",
                                           "ssh_user": "root", "ssh_password": "SEGREDO"}).json()["id"]
        r = c.post(f"/api/servers/{sid}/ssh/test").json()
        assert r["ok"] is False and "recusada" in r["error"]
        assert any(e["kind"] == "ssh_error" for e in m.db.q("SELECT kind FROM events"))
        assert "SEGREDO" not in str(m.db.q("SELECT * FROM events"))


def test_importar_com_ssh():
    from app import importer
    rows, err = importer.parse("nome;url;usuario;senha;ssh_porta;ssh_usuario;ssh_senha\n"
                               "A;a.com:80;u;p;2222;root;x\nB;b.com:80;u;p;;;\nC;c.com:80;u;p;99999;;\nD;d.com:80;u;p;;root;\n")
    assert err is None
    assert rows[0]["ssh_port"] == 2222 and rows[0]["ssh_user"] == "root" and not rows[0]["erro"]
    assert rows[1]["ssh_user"] is None and not rows[1]["erro"]
    assert "porta SSH" in rows[2]["erro"] and "juntos" in rows[3]["erro"]
