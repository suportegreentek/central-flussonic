"""Isola os testes dos dados reais.

Sem isto, `app.main` abriria `./data/central.db` (o banco de verdade, no CT) e os testes escreveriam e
até apagariam registros nele. Aqui o banco e a chave de criptografia vão para uma pasta temporária,
definida ANTES de qualquer import de `app`.
"""
import atexit, os, shutil, tempfile

_tmp = tempfile.mkdtemp(prefix="central-testes-")
atexit.register(shutil.rmtree, _tmp, ignore_errors=True)
os.environ["CENTRAL_DATA_DIR"] = _tmp
os.environ["CENTRAL_DB"] = os.path.join(_tmp, "central.db")
for _k in ("CENTRAL_SECRET_KEY", "CENTRAL_ADMIN_PASSWORD", "CENTRAL_ADMIN_USER"):
    os.environ.pop(_k, None)
