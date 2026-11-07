"""Importação de servidores a partir de planilha CSV (Excel > Salvar como CSV).

Colunas (cabeçalho obrigatório, ordem livre, sem diferenciar acento/maiúscula):
  nome (ou hotel) e endereco (IP ou nome; ou então url completa) são obrigatórias;  porta e protocolo (http/https) são opcionais;  usuario, senha, cidade, api, reinicio_automatico,
  ssh_porta, ssh_usuario, ssh_senha  são opcionais (SSH em branco = usa o padrão das Configurações).
Separador: vírgula, ponto e vírgula ou tab (detectado). Linhas em branco e iniciadas por # são ignoradas.
"""
import csv, io, re, unicodedata
from . import endpoint

MAX_LINHAS = 500
ALIAS = {
    "nome": "name", "hotel": "name", "name": "name", "servidor": "name",
    "url": "url", "base_url": "url",
    "endereco": "host", "ip": "host", "host": "host", "servidor_ip": "host",
    "porta": "port", "port": "port", "porta_api": "port",
    "protocolo": "scheme", "esquema": "scheme", "scheme": "scheme",
    "usuario": "username", "user": "username", "username": "username", "login": "username",
    "senha": "password", "password": "password", "pass": "password",
    "ssh_porta": "ssh_port", "porta_ssh": "ssh_port", "ssh_port": "ssh_port",
    "ssh_usuario": "ssh_user", "ssh_user": "ssh_user", "usuario_ssh": "ssh_user",
    "ssh_senha": "ssh_password", "ssh_password": "ssh_password", "senha_ssh": "ssh_password",
    "cidade": "cidade", "city": "cidade",
    "api": "adapter", "tipo_api": "adapter", "adapter": "adapter",
    "reinicio_automatico": "auto_restart", "reinicio": "auto_restart", "auto_restart": "auto_restart",
}
MODELO = ("nome;endereco;porta;protocolo;usuario;senha;cidade\n"
          "Hotel Exemplo 1;exemplo1.seudominio.com;7777;http;;;São Paulo\n"
          "Hotel Exemplo 2;exemplo2.seudominio.com;7777;http;;;Santos\n")


def _norm(h):
    h = unicodedata.normalize("NFKD", h or "").encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[\s\-]+", "_", h)


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
    if "name" not in head or not ("host" in head or "url" in head):
        return [], "o cabeçalho (primeira linha) precisa ter as colunas nome e endereco (ou url)"
    if len(rows) - 1 > MAX_LINHAS:
        return [], f"máximo de {MAX_LINHAS} linhas por importação"
    out = []
    for n, r in enumerate(rows[1:], start=2):
        d = {}
        for k, v in zip(head, r):
            if k and k not in d:
                d[k] = v.strip()
        item = {"line": n, "name": d.get("name", ""), "cidade": d.get("cidade", ""), "erro": None}
        item["scheme"] = item["host"] = item["port"] = item["base_url"] = None
        erro_end = None
        try:
            sch, host, prt, base = endpoint.resolve(d.get("host") or d.get("url"),
                                                    int(d["port"]) if d.get("port") else None,
                                                    _norm(d.get("scheme", "")) or None)
            item["scheme"], item["host"], item["port"], item["base_url"] = sch, host, prt, base
        except ValueError as e:
            erro_end = str(e) if "int(" not in str(e) and "invalid literal" not in str(e) else "porta inválida (use só números, 1 a 65535)"
        item["username"] = d.get("username") or default_user or ""
        item["password"] = d.get("password") or default_pass or ""
        item["ssh_user"] = d.get("ssh_user") or None
        item["ssh_password"] = d.get("ssh_password") or None
        try:
            item["ssh_port"] = int(d["ssh_port"]) if d.get("ssh_port") else None
            if item["ssh_port"] is not None and not 1 <= item["ssh_port"] <= 65535:
                raise ValueError
            ssh_ok = True
        except ValueError:
            item["ssh_port"], ssh_ok = None, False
        a = _norm(d.get("adapter", "")) or "auto"
        item["adapter"] = {"antiga": "legacy", "legacy": "legacy", "v3": "v3", "auto": "auto", "automatico": "auto"}.get(a)
        item["auto_restart"] = _norm(d.get("auto_restart", "")) in ("sim", "s", "1", "true", "yes", "ligado")
        if not item["name"]:
            item["erro"] = "nome em branco"
        elif erro_end:
            item["erro"] = erro_end
        elif not item["adapter"]:
            item["erro"] = "api inválida (use auto, v3 ou antiga)"
        elif not ssh_ok:
            item["erro"] = "porta SSH inválida (1 a 65535)"
        elif bool(item["ssh_user"]) != bool(item["ssh_password"]):
            item["erro"] = "SSH: informe usuário e senha juntos (ou deixe os dois em branco para usar o padrão)"
        elif not item["username"] or not item["password"]:
            item["erro"] = "sem usuário/senha (informe na linha ou nos campos padrão)"
        out.append(item)
    return out, None
