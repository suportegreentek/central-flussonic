"""ETAPA DE DESCOBERTA — rode contra um servidor de cada versão (somente leitura, só GET).

  python tools/discover.py http://IP:8080 --user USER --password PASS --out discovery_output/hotel-x-23.01

Sonda caminhos candidatos, salva cada resposta JSON bruta (credenciais NÃO são gravadas) e imprime
um resumo: quais endpoints responderam, chaves de topo, chaves de `stats`, tipos/unidades prováveis.
Envie a pasta de saída (ou o resumo) para ajustar app/adapters/profiles.py.
"""
import argparse, json, os, re, sys
import httpx

CANDIDATES = [
    "/streamer/api/v3/schema",  # OpenAPI do PRÓPRIO servidor: a fonte da verdade por versão
    "/streamer/api/v3/streams?limit=5", "/streamer/api/v3/config", "/streamer/api/v3/config/stats",
    "/streamer/api/v3/monitoring/readiness", "/streamer/api/v2/streams", "/streamer/api/v1/streams",
    "/flussonic/api/media", "/flussonic/api/server", "/flussonic/api/config", "/flussonic/api/sessions",
    "/flussonic/api/stats",
]


def analyze_schema(sch):
    """Mostra os endpoints de streams (inclui o de restart, se houver) e os campos de stats com descrição."""
    print("\n== OpenAPI do servidor ==")
    print("versão da API:", sch.get("info", {}).get("version"))
    for path, ops in sorted(sch.get("paths", {}).items()):
        if "stream" in path and "dvr" not in path:
            for m, op in ops.items():
                if isinstance(op, dict):
                    print(f"  {m.upper():6} {path}  [{op.get('operationId', '')}]")
    for name, comp in sch.get("components", {}).get("schemas", {}).items():
        props = comp.get("properties", {}) if isinstance(comp, dict) else {}
        if name.endswith("stream_stats") or {"ts_delay", "alive", "bitrate"} <= set(props):
            print(f"\n  campos de {name}:")
            for k in sorted(props):
                if k in ("alive", "running", "status", "bitrate", "input_bitrate", "ts_delay", "delay", "lag",
                         "opened_at", "start_running_at", "lifetime", "retry_count", "input_error_rate",
                         "source_id", "url", "media_info", "last_dts", "last_dts_at"):
                    d = props[k]
                    desc = (d.get("description") or "").replace("\n", " ")[:110]
                    print(f"    {k:18} {d.get('type', d.get('$ref', ''))!s:10} {d.get('x-api-unit', d.get('format', ''))} {desc}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--user", default=""); ap.add_argument("--password", default="")
    ap.add_argument("--token", default="", help="usa Authorization: Bearer")
    ap.add_argument("--out", default="discovery_output"); ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--stream", help="nome de um stream (com problema, se possível) para detalhar")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    auth = httpx.BasicAuth(a.user, a.password) if a.user else None
    headers = {"Authorization": f"Bearer {a.token}"} if a.token else {}
    c = httpx.Client(base_url=a.base.rstrip("/"), auth=auth, headers=headers, verify=not a.insecure, timeout=15)
    paths = list(CANDIDATES)
    if a.stream:
        n = re.sub(r"/", "%2F", a.stream)
        paths += [f"/streamer/api/v3/streams/{n}", f"/flussonic/api/media_info/{n}"]
    summary = {}
    for p in paths:
        try:
            r = c.get(p)
        except httpx.HTTPError as e:
            print(f"{p:55} ERRO {type(e).__name__}"); continue
        fn = os.path.join(a.out, re.sub(r"[^A-Za-z0-9]+", "_", p).strip("_") + ".json")
        body = r.text
        try:
            j = r.json(); body = json.dumps(j, indent=2, ensure_ascii=False)
        except ValueError:
            j = None
        open(fn, "w").write(body)
        info = f"HTTP {r.status_code}"
        if isinstance(j, dict):
            info += f" chaves={list(j)[:12]}"
        items = j.get("streams") if isinstance(j, dict) else j
        if isinstance(items, list) and items and isinstance(items[0], dict):
            info += f" | {len(items)} itens; chaves do item={list(items[0])[:20]}"
            st = items[0].get("stats")
            if isinstance(st, dict):
                info += f" | stats={ {k: type(v).__name__ for k, v in st.items()} }"
        print(f"{p:55} {info}")
        summary[p] = r.status_code
        if r.status_code == 401:
            print("   -> autenticação recusada; confira usuário/senha ou método (Basic vs token)")
        if p == "/streamer/api/v3/schema" and r.status_code == 200 and isinstance(j, dict):
            analyze_schema(j)
    json.dump(summary, open(os.path.join(a.out, "_summary.json"), "w"), indent=2)
    print(f"\nRespostas brutas salvas em {a.out}/ — revise antes de compartilhar (podem conter URLs de origem/tokens).")


if __name__ == "__main__":
    sys.exit(main())
