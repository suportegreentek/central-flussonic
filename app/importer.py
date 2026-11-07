"""Importação de servidores a partir de planilha CSV (Excel > Salvar como CSV).

Colunas (cabeçalho obrigatório, ordem livre, sem diferenciar acento/maiúscula):
  nome (ou hotel) e url  são obrigatórias;  usuario, senha, cidade, api, reinicio_automatico  são opcionais.
Separador: vírgula, ponto e vírgula ou tab (detectado). Linhas em branco e iniciadas por # são ignoradas.
"""
import csv, io, re, unicodedata
from urllib.parse import urlsplit

MAX_LINHAS = 500
ALIAS = {
    "nome": "name", "hotel": "name", "name": "name", "servidor": "name",
    "url": "base_url", "endereco": "base_url", "base_url": "base_url", "ip": "base_url", "host": "base_url",
    "usuario": "username", "user": "username", "username": "username", "login": "username",
    "senha": "password", "password": "password", "pass": "password",
    "cidade": "cidade", "city": "cidade",
    "api": "adapter", "tipo_api": "adapter", "adapter": "adapter",
    "reinicio_automatico": "auto_restart", "reinicio": "auto_restart", "auto_restart": "auto_restart",
}
MODELO = ("nome;url;usuario;senha;cidade\n"
          "Hotel Exemplo 1;http://exemplo1.seudominio.com:7777;;;São Paulo\n"
          "Hotel Exemplo 2;http://exemplo2.seudominio.com:7777;;;Santos\n")


def _norm(h):
    h = unicodedata.normalize("NFKD", h or "").encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[\s\-]+", "_", h)


def _url(v):
    v = (v or "").strip()
    if v and "://" not in v:
        v = "http://" + v
    p = urlsplit(v)
    if p.scheme not in ("http", "https") or not p.hostname:
        return None
    return v.rstrip("/")


def parse(text, default_user=None, default_pass=None):
    """Devolve (linhas, erro_geral). Cada linha: dict com line, name, base_url, username, password, cidade,
    adapter, auto_restart e erro (None se válida)."""
    text = (text or "").lstrip("﻿")
    if len(text) > 1_000_000:
        return [], "arquivo grande demais (máx. 1 MB)"
    linhas = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not linhas:
        return [], "arquivo vazio"
    delim = max((";", ",", "\t"), key=lambda d: linhas[0].count(d))
    rows = list(csv.reader(io.StringIO("\n".join(linhas)), delimiter=delim))
    head = [ALIAS.get(_norm(h)) for h in rows[0]]
    if "name" not in head or "base_url" not in head:
        return [], "o cabeçalho (primeira linha) precisa ter as colunas nome e url"
    if len(rows) - 1 > MAX_LINHAS:
        return [], f"máximo de {MAX_LINHAS} linhas por importação"
    out = []
    for n, r in enumerate(rows[1:], start=2):
        d = {}
        for k, v in zip(head, r):
            if k and k not in d:
                d[k] = v.strip()
        item = {"line": n, "name": d.get("name", ""), "cidade": d.get("cidade", ""), "erro": None}
        item["base_url"] = _url(d.get("base_url"))
        item["username"] = d.get("username") or default_user or ""
        item["password"] = d.get("password") or default_pass or ""
        a = _norm(d.get("adapter", "")) or "auto"
        item["adapter"] = {"antiga": "legacy", "legacy": "legacy", "v3": "v3", "auto": "auto", "automatico": "auto"}.get(a)
        item["auto_restart"] = _norm(d.get("auto_restart", "")) in ("sim", "s", "1", "true", "yes", "ligado")
        if not item["name"]:
            item["erro"] = "nome em branco"
        elif not item["base_url"]:
            item["erro"] = "url inválida (use http://endereco:porta)"
        elif not item["adapter"]:
            item["erro"] = "api inválida (use auto, v3 ou antiga)"
        elif not item["username"] or not item["password"]:
            item["erro"] = "sem usuário/senha (informe na linha ou nos campos padrão)"
        out.append(item)
    return out, None
