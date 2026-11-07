"""Servidor Flussonic FALSO para testar a central (formato inspirado na API, não oficial).

Uso:  python tools/fake_flussonic.py --port 9101 --mode v3 [--user admin --password pass]
Simular falha (stream fica em erro, atraso alto, sem bitrate):
  curl -X POST 'http://localhost:9101/_sim/ch1?state=error'     # error | lag | zero | ok
O restart (POST v3 / GET legacy) volta o stream para ok, salvo `?sticky=1` na simulação
(stream continua com problema mesmo após reinício, para testar o limite de tentativas).
"""
import argparse, base64, time
from fastapi import FastAPI, Request, Response
import uvicorn

p = argparse.ArgumentParser()
p.add_argument("--port", type=int, default=9101)
p.add_argument("--mode", choices=["v3", "legacy"], default="v3")
p.add_argument("--user", default="")
p.add_argument("--password", default="")
args = p.parse_args()

app = FastAPI()
T0 = time.time() - 4 * 86400
STREAMS = {n: {"state": "ok", "sticky": False, "opened": T0} for n in ("ch1", "ch2", "hotel/ch3")}
RESTARTS = []


@app.middleware("http")
async def auth(request: Request, call_next):
    if args.user and not request.url.path.startswith("/_sim"):
        h = request.headers.get("authorization", "")
        want = "Basic " + base64.b64encode(f"{args.user}:{args.password}".encode()).decode()
        if h != want:
            return Response("unauthorized", 401)
    return await call_next(request)


def render(name, s):
    st = s["state"]
    # campos conforme o exemplo do manual (stats.alive, opened_at em ms, retry_count...) + bitrate/ts_delay
    stats = {"alive": True, "running": True, "bitrate": 2500, "ts_delay": 200, "retry_count": 0,
             "input_error_rate": 0, "opened_at": int(s["opened"] * 1000), "start_running_at": int(s["opened"] * 1000)}
    if st == "error":   # processo vivo (uptime alto), sem dados e com atraso de 4h
        stats.update(alive=False, ts_delay=4 * 3600 * 1000)
        stats.pop("bitrate")
    elif st == "lag":   # hipótese: dados chegando, timestamps atrasados
        stats.update(ts_delay=4 * 3600 * 1000)
    elif st == "zero":
        stats.update(bitrate=0)
    return {"name": name, "static": True, "stats": stats, "inputs": [{"url": "m4s://gs1.example/x"}, {"url": "m4s://gs2.example/x"}]}


@app.post("/_sim/{name:path}")
def sim(name: str, state: str = "error", sticky: bool = False):
    STREAMS[name]["state"], STREAMS[name]["sticky"] = state, sticky
    return {"ok": True}


@app.get("/_sim")
def sim_info():
    return {"restarts": RESTARTS}


def do_restart(name):
    RESTARTS.append((time.time(), name))
    if not STREAMS[name]["sticky"]:
        STREAMS[name]["state"] = "ok"
        STREAMS[name]["opened"] = time.time()
    return {"ok": True}


if args.mode == "v3":
    @app.get("/streamer/api/v3/streams")
    def l():
        return {"streams": [render(n, s) for n, s in STREAMS.items()]}

    @app.get("/streamer/api/v3/streams/{name:path}")
    def g(name: str):
        return render(name, STREAMS[name])

    @app.get("/flussonic/api/stream_restart/{name:path}")  # igual ao Streamer 21.10 real
    def r(name: str):
        return do_restart(name)

    @app.get("/streamer/api/v3/config")
    def c():
        return {"version": "23.01-fake"}
else:
    @app.get("/flussonic/api/media")
    def lm():
        return [render(n, s) for n, s in STREAMS.items()]

    @app.get("/flussonic/api/media_info/{name:path}")
    def gm(name: str):
        return render(name, STREAMS[name])

    @app.get("/flussonic/api/stream_restart/{name:path}")
    def rm(name: str):
        return do_restart(name)

    @app.get("/flussonic/api/server")
    def sv():
        return {"version": "21.10-fake"}

uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
