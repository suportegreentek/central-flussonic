"""Endereço de um servidor separado em protocolo, host e porta (e a montagem da URL base usada pelos adaptadores)."""
from urllib.parse import urlsplit


def split(text):
    """Aceita "host", "host:porta", "http://host:porta" ou "https://host/caminho".
    Devolve (scheme|None, host, porta|None). Levanta ValueError com mensagem em português."""
    t = (text or "").strip()
    if not t:
        raise ValueError("endereço em branco")
    p = urlsplit(t if "://" in t else "//" + t)
    if p.scheme and p.scheme not in ("http", "https"):
        raise ValueError("protocolo deve ser http ou https")
    try:
        port = p.port
    except ValueError:
        raise ValueError("porta inválida (1 a 65535)") from None
    if not p.hostname or any(c.isspace() for c in p.hostname):
        raise ValueError("endereço inválido (informe o IP ou o nome do servidor)")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("porta inválida (1 a 65535)")
    return (p.scheme or None), p.hostname, port


def resolve(host=None, port=None, scheme=None, base_url=None):
    """Junta o que foi informado nos campos separados com o que veio numa URL completa (campos separados vencem).
    Devolve (scheme, host, port, base_url)."""
    s0 = h0 = p0 = None
    src = host or base_url
    if src:
        s0, h0, p0 = split(src)
    if not h0:
        raise ValueError("informe o endereço do servidor")
    sch = (scheme or s0 or "http").lower()
    if sch not in ("http", "https"):
        raise ValueError("protocolo deve ser http ou https")
    prt = int(port) if port else p0
    if prt is not None and not 1 <= prt <= 65535:
        raise ValueError("porta inválida (1 a 65535)")
    return sch, h0, prt, compose(sch, h0, prt)


def compose(scheme, host, port):
    return f"{scheme}://{host}" + (f":{port}" if port else "")
