"""Perfis de API por geração do Flussonic. AJUSTAR após a etapa de descoberta.

Status: TODOS os valores abaixo são hipóteses de trabalho (não verificadas).
"""
AUTO_ORDER = ["v3", "legacy"]

PROFILES = {
    # Hipótese: 23.01 (e talvez 21.11+) expõe a API v3 em /streamer/api/v3.
    "v3": {
        "list_path": "/streamer/api/v3/streams",
        "list_key": "streams",
        "list_params": {"limit": 100},
        "cursor_param": "cursor",
        "next_key": "next",
        "get_path": "/streamer/api/v3/streams/{name}",
        "restart_method": "POST",
        "restart_path": "/streamer/api/v3/streams/{name}/restart",
        "version_paths": ["/streamer/api/v3/config", "/streamer/api/v3/config/stats"],
        "status_keys": ["status", "state"],
        "bitrate_keys": ["input_bitrate", "bitrate"],
        "lag_keys": [("lag_ms", 1000.0), ("lag", 1.0), ("ts_delay", 1.0)],
        "opened_at_keys": ["opened_at", "started_at"],
    },
    # Hipótese: 21.10 usa a API antiga /flussonic/api (v2/legada).
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
