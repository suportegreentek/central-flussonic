"""Canais de notificação extensíveis. Para adicionar um canal: crie uma classe com
`async send(event)` e registre em CHANNEL_TYPES."""
import asyncio, logging, smtplib
from email.message import EmailMessage
import httpx

log = logging.getLogger("notify")
LEVELS = {"info": 0, "warning": 1, "critical": 2}


def _text(ev):
    stream = f"{ev['stream']} ({ev['stream_title']})" if ev.get("stream") and ev.get("stream_title") else ev.get("stream")
    where = " / ".join(x for x in (ev.get("server_name"), stream) if x)
    return f"[{ev['level'].upper()}] {where + ': ' if where else ''}{ev['message']} ({ev['ts']} UTC)"


class Webhook:
    def __init__(self, cfg): self.url = cfg["url"]
    async def send(self, ev):
        async with httpx.AsyncClient(timeout=10) as c:
            (await c.post(self.url, json={"text": _text(ev), "event": ev})).raise_for_status()


class NotifyError(Exception):
    """Erro com mensagem segura para exibir (sem segredos)."""


class Telegram:
    def __init__(self, cfg): self.token, self.chat = cfg["bot_token"], cfg["chat_id"]
    async def send(self, ev):
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                             json={"chat_id": self.chat, "text": _text(ev)})
            if r.status_code >= 400:  # a descrição do Telegram não contém o token; a URL sim, então não propagamos o erro do httpx
                try:
                    desc = r.json().get("description", "")
                except ValueError:
                    desc = ""
                raise NotifyError(f"Telegram recusou (HTTP {r.status_code}): {desc[:150]}")


class Email:
    def __init__(self, cfg): self.cfg = cfg
    def _send(self, ev):
        c = self.cfg
        m = EmailMessage()
        m["Subject"] = f"[Greentek] {ev['level']} - {ev['kind']}"
        m["From"], m["To"] = c["from"], c["to"]
        m.set_content(_text(ev))
        with smtplib.SMTP(c["host"], int(c.get("port", 587)), timeout=15) as s:
            if c.get("starttls", True): s.starttls()
            if c.get("username"): s.login(c["username"], c.get("password", ""))
            s.send_message(m)
    async def send(self, ev): await asyncio.to_thread(self._send, ev)


CHANNEL_TYPES = {"webhook": Webhook, "telegram": Telegram, "email": Email}


# Tipos que também são avisados mesmo sendo "info" (para canais com nível mínimo info ou warning).
NOTIFY_ALSO = {"recovered"}
GROUP_LIMIT = 3      # acima disso, os eventos do mesmo tipo viram UMA mensagem-resumo por ciclo
KIND_TXT = {"problem": "com problema persistente", "auto_restart": "reiniciados automaticamente",
            "restart_failed": "continuam com problema após o reinício", "restart_limit": "atingiram o limite de reinícios",
            "restart_error": "falha ao reiniciar", "recovered": "recuperados", "server_offline": "servidores inacessíveis"}


def wants(ch, ev):
    mn = LEVELS.get(ch["min_level"], 1)
    return LEVELS.get(ev["level"], 0) >= mn or (ev["kind"] in NOTIFY_ALSO and mn <= 1)


def summarize(kind, evs):
    """Junta vários eventos do mesmo tipo em uma mensagem: agrupa pelo nome do stream (ou título) e lista os hotéis."""
    groups = {}
    for e in evs:
        label = e.get("stream_title") or e.get("stream") or "(servidor)"
        groups.setdefault(label, []).append(e.get("server_name") or "?")
    lines = []
    for label, hotels in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:12]:
        names = ", ".join(hotels[:8]) + (f" e mais {len(hotels) - 8}" if len(hotels) > 8 else "")
        lines.append(f"• {label}: {len(hotels)} — {names}" if label != "(servidor)" else f"• {names}")
    if len(groups) > 12:
        lines.append(f"… e mais {len(groups) - 12} grupos")
    lv = max((e["level"] for e in evs), key=lambda x: LEVELS.get(x, 0))
    msg = f"{len(evs)} {KIND_TXT.get(kind, kind)}\n" + "\n".join(lines)
    return {"level": lv, "kind": kind, "server_name": None, "stream": None, "stream_title": None,
            "ts": evs[-1]["ts"], "message": msg[:3500]}


def build_messages(evs):
    by = {}
    for e in evs:
        by.setdefault(e["kind"], []).append(e)
    out = []
    for kind, lst in by.items():
        out += lst if len(lst) <= GROUP_LIMIT else [summarize(kind, lst)]
    return out


class Notifier:
    def __init__(self, db):
        self.db = db
        self.queue = []
        self.batching = False   # True durante o ciclo de coleta: os eventos esperam e saem agrupados em flush()

    async def enqueue(self, ev):
        self.queue.append(ev)
        if not self.batching:
            await self.flush()

    async def flush(self):
        events, self.queue = self.queue, []
        if not events:
            return
        for ch in self.db.q("SELECT * FROM channels WHERE enabled=1"):
            for m in build_messages([e for e in events if wants(ch, e)]):
                await self._deliver(ch, m)

    async def dispatch(self, ev):
        for ch in self.db.q("SELECT * FROM channels WHERE enabled=1"):
            if wants(ch, ev):
                await self._deliver(ch, ev)

    async def _deliver(self, ch, ev):
        err = await self.send_one(ch, ev)
        if err:  # uma segunda tentativa cobre falha de rede passageira
            await asyncio.sleep(2)
            err = await self.send_one(ch, ev)
        if err:  # a falha precisa aparecer na tela (antes só ia para o log e o alerta sumia sem rastro)
            try:
                self.db.add_event("info", "notify_error",
                                  f"Não consegui enviar o alerta pelo canal '{ch['name']}': {err}",
                                  None, None, {"canal": ch["name"], "evento": ev.get("kind"),
                                               "servidor": ev.get("server_name"), "stream": ev.get("stream")})
            except Exception:
                log.exception("falha ao registrar erro de notificação")

    async def send_one(self, ch, ev):
        from .crypto import decrypt_obj
        try:
            await CHANNEL_TYPES[ch["type"]](decrypt_obj(ch["config_enc"])).send(ev)
            return None
        except Exception as e:  # nunca logar a configuração (contém segredos)
            msg = str(e) if isinstance(e, NotifyError) else f"{type(e).__name__}"
            log.warning("falha ao notificar canal %s: %s", ch["name"], msg)
            return msg
