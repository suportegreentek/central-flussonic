"""Camada de adaptação da API do Flussonic.

Os perfis (caminhos/campos) ficam em `profiles.py`, marcados como confirmados pelo manual
ou hipóteses. Confirme por versão com `tools/discover.py` (veja docs/DISCOVERY.md).
"""
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote

import httpx

from . import profiles


class AdapterError(Exception):
    def __init__(self, msg, status=None):
        super().__init__(msg)
        self.status = status


# Endereço de reinício que funcionou, por (servidor, perfil), para não retestar a cada vez.
_RESTART_OK: dict = {}


@dataclass
class NormStream:
    name: str
    status: Optional[str]
    bitrate: Optional[float]      # kbit/s (unidade a confirmar na descoberta)
    lag_s: Optional[float]        # atraso em segundos
    uptime_s: Optional[float]
    static: Optional[bool]
    alive: Optional[bool] = None
    raw: dict = field(default_factory=dict)


def _first(d: dict, keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k], k
    return None, None


def normalize(raw: dict, prof: dict, now: Optional[float] = None) -> NormStream:
    now = now or time.time()
    stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
    name = raw.get("name") or raw.get("id") or ""
    status, _ = _first(stats, prof["status_keys"])
    if status is None:
        status, _ = _first(raw, prof["status_keys"])
    alive = stats.get("alive") if isinstance(stats.get("alive"), bool) else None
    if status is None and alive is not None:  # [C] stats.alive existe; não há stats.status no manual
        status = "running" if alive else "error"
    bitrate, _ = _first(stats, prof["bitrate_keys"])
    if bitrate is None:
        bitrate, _ = _first(raw, prof["bitrate_keys"])
    lag = None
    for key, div in prof["lag_keys"]:  # (campo, divisor para segundos)
        v = stats.get(key, raw.get(key))
        if isinstance(v, (int, float)):
            lag = v / div
            break
    uptime = None
    opened, _ = _first(stats, prof["opened_at_keys"])
    if isinstance(opened, (int, float)) and opened > 0:
        opened = opened / 1000 if opened > 1e11 else opened  # ms -> s
        uptime = max(0.0, now - opened)
    static = raw.get("static")
    if not isinstance(static, bool) and isinstance(raw.get("effective"), dict):
        static = raw["effective"].get("static")
    return NormStream(name=name, status=str(status).lower() if status is not None else None,
                      bitrate=float(bitrate) if isinstance(bitrate, (int, float)) else None,
                      lag_s=lag, uptime_s=uptime, static=static if isinstance(static, bool) else None, alive=alive, raw=raw)


class Adapter:
    def __init__(self, base_url: str, auth_type: str, creds: dict, timeout: float, verify_tls: bool,
                 profile: str, client: Optional[httpx.AsyncClient] = None):
        self.base = base_url.rstrip("/")
        self.prof = profiles.PROFILES[profile]
        self.profile = profile
        self.timeout = timeout
        headers, auth = {}, None
        if auth_type == "basic":
            auth = httpx.BasicAuth(creds.get("username", ""), creds.get("password", ""))
        elif auth_type == "bearer":
            headers["Authorization"] = f"Bearer {creds.get('token', '')}"
        self._own = client is None
        self.client = client or httpx.AsyncClient(timeout=timeout, verify=verify_tls, auth=auth,
                                                  headers=headers, follow_redirects=True)

    async def close(self):
        if self._own:
            await self.client.aclose()

    async def _req(self, method, path, **kw):
        try:
            r = await self.client.request(method, self.base + path, timeout=self.timeout, **kw)
        except httpx.HTTPError as e:  # nunca incluir credenciais na mensagem
            raise AdapterError(f"{type(e).__name__}: {str(e)[:200]}") from None
        if r.status_code in (401, 403):
            raise AdapterError(f"autenticação recusada (HTTP {r.status_code})")
        if r.status_code >= 400:
            raise AdapterError(f"HTTP {r.status_code} em {path}", status=r.status_code)
        return r

    @staticmethod
    def _items(data, key):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            v = data.get(key)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):  # mapa nome -> objeto
                return [dict(x, name=x.get("name", n)) for n, x in v.items()]
        raise AdapterError("formato de lista de streams inesperado")

    async def list_streams(self) -> list[NormStream]:
        p, out, cursor, pages = self.prof, [], None, 0
        while True:
            params = dict(p.get("list_params", {}))
            if cursor and p.get("cursor_param"):
                params[p["cursor_param"]] = cursor
            r = await self._req("GET", p["list_path"], params=params)
            try:
                data = r.json()
            except ValueError:
                raise AdapterError("resposta não é JSON") from None
            out += [normalize(x, p) for x in self._items(data, p["list_key"]) if isinstance(x, dict)]
            cursor = data.get(p.get("next_key", "next")) if isinstance(data, dict) else None
            pages += 1
            if not cursor or pages > 100:
                return out

    async def get_stream_raw(self, name: str) -> Any:
        p = self.prof
        r = await self._req("GET", p["get_path"].format(name=quote(name, safe="")))
        return r.json()

    async def restart(self, name: str) -> dict:
        cands = list(self.prof["restart_candidates"])
        key = (self.base, self.profile)
        if key in _RESTART_OK and _RESTART_OK[key] in cands:  # tenta primeiro o que já funcionou
            cands.remove(_RESTART_OK[key])
            cands.insert(0, _RESTART_OK[key])
        tried = []
        for method, path in cands:
            p = path.format(name=quote(name, safe=""))
            try:
                r = await self._req(method, p)
            except AdapterError as e:
                if e.status in (404, 405):  # endereço não existe nesta versão: tenta o próximo
                    tried.append(f"{method} {path}")
                    continue
                raise
            if r.text.strip().lower() == "false":
                raise AdapterError("servidor respondeu false ao reinício")
            _RESTART_OK[key] = (method, path)
            return {"http_status": r.status_code, "body": r.text[:500], "endpoint": f"{method} {path}"}
        raise AdapterError("nenhum endereço de reinício aceito por este servidor (tentados: " + "; ".join(tried) + ")")

    async def detect_version(self) -> Optional[str]:
        for path in self.prof.get("version_paths", []):
            try:
                r = await self._req("GET", path)
                d = r.json()
                for k in ("version", "server_version", "flussonic_version"):
                    if isinstance(d, dict) and d.get(k):
                        return str(d[k])
            except (AdapterError, ValueError):
                continue
        return None


async def build_for_server(server: dict, creds: dict, timeout: float, client=None) -> Adapter:
    """Escolhe o perfil. 'auto' tenta v3 e cai para legacy se a lista falhar."""
    choice = server.get("adapter") or "auto"
    order = [choice] if choice != "auto" else list(profiles.AUTO_ORDER)
    last = None
    for prof in order:
        a = Adapter(server["base_url"], server["auth_type"], creds, timeout, bool(server["verify_tls"]), prof, client)
        if choice != "auto":
            return a
        try:
            await a.list_streams()
            return a
        except AdapterError as e:
            last = e
            await a.close()
            if "autenticação" in str(e) or "Timeout" in str(e) or "Connect" in str(e):
                break
    raise last or AdapterError("nenhum perfil funcionou")
