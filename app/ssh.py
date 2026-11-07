"""Acesso SSH aos servidores (reiniciar o serviço Flussonic ou o servidor inteiro).

Credenciais: as do servidor (se tiver usuário próprio) sobrescrevem as padrão das Configurações.
Senhas ficam criptografadas (Fernet) e nunca voltam pela API nem entram em logs/eventos."""
import json
from urllib.parse import urlsplit
from .crypto import decrypt_obj, encrypt_obj

SERVICE = "flussonic"
# O comando roda em segundo plano e só depois de 2 s, para a conexão SSH fechar limpa antes do reinício.
CMD_REBOOT = "(sleep 2; reboot) >/dev/null 2>&1 &"
CMD_SERVICE = f"systemctl restart {SERVICE} || service {SERVICE} restart"


class SSHError(Exception):
    """Mensagem segura para exibir (sem senha)."""


# padrão (Configurações) -------------------------------------------------------
def get_default(db):
    r = {x["key"]: x["value"] for x in db.q("SELECT key,value FROM settings WHERE key LIKE 'ssh_default_%'")}
    return {"port": json.loads(r["ssh_default_port"]) if r.get("ssh_default_port") else 22,
            "user": json.loads(r["ssh_default_user"]) if r.get("ssh_default_user") else "",
            "password_enc": json.loads(r["ssh_default_pass_enc"]) if r.get("ssh_default_pass_enc") else None}


def set_default(db, port=None, user=None, password=None, clear=False):
    def put(k, v):
        db.x("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, json.dumps(v)))
    if clear:
        db.x("DELETE FROM settings WHERE key LIKE 'ssh_default_%'")
        return
    if port is not None:
        put("ssh_default_port", int(port))
    if user is not None:
        put("ssh_default_user", user.strip())
    if password:
        put("ssh_default_pass_enc", encrypt_obj({"password": password}))


def resolve(server, default):
    """Devolve (host, port, user, senha). Usuário+senha do servidor sobrescrevem o par padrão; a porta é independente."""
    host = server.get("host") or urlsplit(server["base_url"]).hostname
    port = server.get("ssh_port") or default["port"] or 22
    if server.get("ssh_user") and server.get("ssh_pass_enc"):
        user, enc = server["ssh_user"], server["ssh_pass_enc"]
    else:
        user, enc = default["user"], default["password_enc"]
    if not (host and user and enc):
        raise SSHError("SSH não configurado: informe usuário e senha no servidor ou em Configurações (SSH padrão)")
    return host, int(port), user, decrypt_obj(enc).get("password", "")


def configured(server, default):
    try:
        resolve(server, default)
        return True
    except SSHError:
        return False


# execução ---------------------------------------------------------------------
async def run(host, port, user, password, command, timeout=20):
    """Executa um comando e devolve o código de saída. Troca de exceções por SSHError seguro."""
    import asyncssh
    try:
        # known_hosts=None: não verifica a identidade do servidor (rede interna); limitação registrada na documentação
        async with asyncssh.connect(host, port=port, username=user, password=password, known_hosts=None,
                                    connect_timeout=timeout, login_timeout=timeout) as conn:
            if user != "root":  # fora do root, usa sudo lendo a senha da entrada padrão
                command = "sudo -S -p '' sh -c " + _q(command)
                res = await conn.run(command, input=password + "\n", check=False, timeout=timeout)
            else:
                res = await conn.run(command, check=False, timeout=timeout)
            return res.exit_status
    except asyncssh.PermissionDenied:
        raise SSHError("autenticação SSH recusada (usuário ou senha)") from None
    except asyncssh.Error as e:
        raise SSHError(f"erro SSH: {type(e).__name__}") from None
    except (OSError, TimeoutError) as e:
        raise SSHError(f"não consegui conectar em {host}:{port} ({type(e).__name__})") from None
    except Exception as e:
        if type(e).__name__ == "TimeoutError":
            raise SSHError(f"tempo esgotado em {host}:{port}") from None
        raise SSHError(f"erro SSH: {type(e).__name__}") from None


def _q(s):
    return "'" + s.replace("'", "'\\''") + "'"
