"""Configuração por variáveis de ambiente (bootstrap). Parâmetros operacionais
(intervalo, limites, etc.) ficam no banco e são editáveis pela interface."""
import os

DATA_DIR = os.environ.get("CENTRAL_DATA_DIR", "data")
DB_PATH = os.environ.get("CENTRAL_DB", os.path.join(DATA_DIR, "central.db"))
SECRET_KEY = os.environ.get("CENTRAL_SECRET_KEY")  # chave Fernet (base64 32 bytes)
ADMIN_USER = os.environ.get("CENTRAL_ADMIN_USER", "")
ADMIN_PASSWORD = os.environ.get("CENTRAL_ADMIN_PASSWORD", "")
DISPLAY_TZ = "America/Sao_Paulo"

# Valores padrão de configuração operacional (gravados em `settings`).
DEFAULT_SETTINGS = {
    "poll_interval_s": 30,        # intervalo entre coletas
    "request_timeout_s": 10,      # timeout por requisição HTTP
    "concurrency": 8,             # servidores consultados em paralelo
    "delay_threshold_s": 60,      # atraso (lag) acima disso = problema
    "persistence_checks": 3,      # verificações seguidas antes de agir
    "min_restart_interval_s": 300,
    "max_restarts_per_window": 3,
    "restart_window_s": 3600,
    "verify_after_s": 60,         # quando checar se o reinício resolveu
    "events_retention_days": 90,
    "snapshots_retention_days": 180,
}
