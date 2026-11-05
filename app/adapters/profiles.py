"""Perfis de API por geração do Flussonic.

Fonte: manual oficial FMS (fms_en.pdf, © 2025, seção 2.3.3 API) — descreve a versão ATUAL,
não 21.10/23.01. Ver docs/DISCOVERY.md para o que está confirmado e o que falta.
[C] = confirmado no manual   [H] = hipótese, confirmar com tools/discover.py (lê /streamer/api/v3/schema)
"""
AUTO_ORDER = ["v3", "legacy"]

PROFILES = {
    "v3": {
        "list_path": "/streamer/api/v3/streams",          # [C]
        "list_key": "streams",                            # [C] {"streams":[...],"next","prev","estimated_count"}
        "list_params": {"limit": 100},                    # [C] limit=
        "cursor_param": "cursor",                         # [C] valor de "next" vai em cursor=
        "next_key": "next",                               # [C]
        "get_path": "/streamer/api/v3/streams/{name}",    # [C] "/" do nome codificado como %2F
        "restart_method": "POST",                         # [H] não consta no manual; ver schema do servidor
        "restart_path": "/streamer/api/v3/streams/{name}/restart",  # [H]
        "version_paths": ["/streamer/api/v3/config", "/streamer/api/v3/config/stats"],  # [C] existem; campo de versão [H]
        "status_keys": ["status", "state"],               # [H] o manual não mostra stats.status
        "bitrate_keys": ["bitrate", "input_bitrate"],     # [C] stats.bitrate (usado em filtro); unidade [H] kbit/s
        # [C] stats.ts_delay (sort) e stats.delay (filtro "delay < 5000"); unidade [H] ms
        "lag_keys": [("ts_delay", 1000.0), ("delay", 1000.0), ("lag_ms", 1000.0)],
        "opened_at_keys": ["opened_at", "start_running_at"],  # [C] epoch em ms
    },
    # [H] 21.10: o manual atual não cobre. Pode ter v3 parcial (v3 de streams citada a partir da 21.11)
    # ou só a API antiga /flussonic/api. Tudo aqui é hipótese até rodar tools/discover.py num 21.10.
    "legacy": {
        "list_path": "/flussonic/api/media",
        "list_key": "streams",
        "list_params": {},
        "cursor_param": None,
        "get_path": "/flussonic/api/media_info/{name}",
        "restart_method": "GET",
        "restart_path": "/flussonic/api/stream_restart/{name}",
        "version_paths": ["/flussonic/api/server", "/flussonic/api/config"],
        "status_keys": ["status", "state"],
        "bitrate_keys": ["input_bitrate", "bitrate"],
        "lag_keys": [("lag_ms", 1000.0), ("lag", 1.0), ("ts_delay", 1.0)],
        "opened_at_keys": ["opened_at", "started_at", "start_running_at"],
    },
}
