"""Criptografia em repouso das credenciais (Fernet)."""
import json, os
from cryptography.fernet import Fernet
from . import config

_fernet = None


def _load_key() -> bytes:
    if config.SECRET_KEY:
        return config.SECRET_KEY.encode()
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = os.path.join(config.DATA_DIR, "secret.key")
    if os.path.exists(path):
        return open(path, "rb").read().strip()
    key = Fernet.generate_key()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_key())
    return _fernet


def encrypt_obj(obj) -> str:
    return fernet().encrypt(json.dumps(obj).encode()).decode()


def decrypt_obj(token: str):
    return json.loads(fernet().decrypt(token.encode()).decode()) if token else {}
