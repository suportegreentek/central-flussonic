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
    return f"[{ev['level'].upper()}] {where}: {ev['message']} ({ev['ts']} UTC)"


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


class Notifier:
    def __init__(self, db):
        self.db = db

    async def dispatch(self, ev):
        from .crypto import decrypt_obj
        for ch in self.db.q("SELECT * FROM channels WHERE enabled=1"):
            if LEVELS.get(ev["level"], 0) < LEVELS.get(ch["min_level"], 1):
                continue
            await self.send_one(ch, ev)

    async def send_one(self, ch, ev):
        from .crypto import decrypt_obj
        try:
            await CHANNEL_TYPES[ch["type"]](decrypt_obj(ch["config_enc"])).send(ev)
            return None
        except Exception as e:  # nunca logar a configuração (contém segredos)
            msg = str(e) if isinstance(e, NotifyError) else f"{type(e).__name__}"
            log.warning("falha ao notificar canal %s: %s", ch["name"], msg)
            return msg
