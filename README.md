# Central Flussonic

Painel web que monitora vários servidores Flussonic (um por hotel) pela API HTTP, detecta streams travados
(`error` com fonte online), salva **evidência (JSON bruto)** e reinicia automaticamente com limites.

> ⚠️ **Antes de usar em produção:** autenticação, listagem e campos principais foram confirmados no manual oficial
> (versão atual). O **endpoint de restart** e o comportamento do **21.10** ainda precisam de confirmação. Veja [docs/DISCOVERY.md](docs/DISCOVERY.md).

## Instalação (Docker)
```bash
export CENTRAL_ADMIN_PASSWORD='uma-senha-forte'
docker compose up -d --build
```
Abra http://SERVIDOR:8000 (usuário `admin`). Dados em `./data` (SQLite + `secret.key`). **Faça backup de `./data`**
(sem `secret.key` as credenciais cadastradas não podem ser lidas). Sem Docker: `pip install -r requirements.txt && uvicorn app.main:app`.

## Configuração
- Variáveis: `CENTRAL_ADMIN_USER/PASSWORD` (protege UI e API), `CENTRAL_SECRET_KEY` (chave Fernet opcional), `CENTRAL_DATA_DIR`.
- Aba **Configurações**: intervalo de coleta, timeout, concorrência, limite de atraso, persistência (N verificações),
  intervalo mínimo entre reinícios, máx. de reinícios por janela, retenção. Aplicadas no próximo ciclo.
- Canais de notificação (webhook, Telegram, e-mail). Novos canais: classe em `app/notify.py` + `CHANNEL_TYPES`.
- Credenciais dos servidores: criptografadas (Fernet) no banco, nunca retornadas pela API nem logadas.
- Horários: gravados em UTC, exibidos em America/Sao_Paulo.

## Adicionar servidores
Aba **Servidores** → nome, protocolo, endereço (IP ou nome) e porta (ex.: 8080), autenticação (HTTP Basic; para o reinício funcionar use o
usuário de **`edit_auth`**, porque `view_auth` só permite leitura), hotel/cidade → **Testar** (somente leitura) →
marque "reinício automático" se desejado. O padrão é *desligado*. Por stream, a visão geral permite herdar / ligar / desligar.

## Como funciona
1. A cada intervalo, cada servidor é consultado em paralelo (limite de concorrência, timeout). Servidor fora = "offline"; não afeta os demais.
2. Problema = status com erro / `stats.alive=false`, bitrate 0/ausente (ignorado se o stream é `static:false`) ou atraso > limite.
3. Após N verificações seguidas: evento `problem` + notificação. Com auto-restart ligado: snapshot → restart (único write) → evento.
4. Respeita intervalo mínimo e limite por janela; ao estourar, evento **critical** `restart_limit` e para de tentar naquele stream até se recuperar.
5. Após `verify_after_s`, registra `restart_ok` ou `restart_failed`.
Evidências: aba **Evidências** (baixar JSON para o suporte Flussonic).

## Testes
```bash
python -m pytest -q          # lógica de detecção/persistência/limites/criptografia
```
**Simular stream em erro (ponta a ponta):**
```bash
python tools/fake_flussonic.py --port 9101 --mode v3 --user admin --password pw &   # mock 23.01
python tools/fake_flussonic.py --port 9102 --mode legacy &                          # mock 21.10
CENTRAL_ADMIN_PASSWORD=x uvicorn app.main:app &
# cadastre http://127.0.0.1:9101 (basic admin/pw) e http://127.0.0.1:9102 (none); reduza poll_interval_s=2, persistence_checks=2
curl -X POST 'http://127.0.0.1:9101/_sim/ch1?state=error'            # ch1 entra em erro
curl -X POST 'http://127.0.0.1:9101/_sim/ch1?state=error&sticky=true' # não se recupera com restart → testa limite/alerta crítico
curl http://127.0.0.1:9101/_sim                                       # lista reinícios recebidos
```
O mock **não** é a API oficial; ele só exercita a central.

## Limitações conhecidas
- Perfis de API não validados em servidores reais (ver DISCOVERY).
- Sem teste real da hipótese "timestamps atrasados": os snapshots pré-restart existem justamente para isso.
- Notificações Telegram/e-mail não testadas contra serviços reais.
