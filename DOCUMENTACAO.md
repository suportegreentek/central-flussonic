# DOCUMENTAÇÃO

> Versão atual: ver `app/version.py`. Esquema de capítulos ATA 100: ainda não definido (ver `REGRAS.md`, seção 2.5); este arquivo segue por ora o formato simples.

## Como o sistema funciona

**Finalidade.** Central web da Greentek que monitora e gerencia os servidores de streaming dos hotéis pela API HTTP de cada servidor.

**Componentes** (pasta `app/`):
- `main.py`: servidor web (FastAPI). A API fica em `/api` e é protegida por usuário e senha (`CENTRAL_ADMIN_USER` / `CENTRAL_ADMIN_PASSWORD`). A interface é `static/index.html`.
- `monitor.py`: coleta periódica de todos os servidores em paralelo (concorrência e tempo limite configuráveis). Um servidor offline não afeta os demais.
- `adapters/`: camada por versão do servidor. `profiles.py` guarda caminhos e campos por perfil (`v3`, `legacy`); o modo automático testa `v3` e cai para `legacy`.
- `db.py`: banco SQLite (horários em UTC; a interface mostra America/Sao_Paulo).
- `crypto.py`: credenciais dos servidores criptografadas em repouso (chave em `data/secret.key` ou `CENTRAL_SECRET_KEY`). Nunca vão para logs.
- `notify.py`: canais de notificação (webhook, Telegram, e-mail).
- `version.py`: fonte única da versão.

**Detecção de problema.** Um stream é considerado com problema quando o estado indica erro, o bitrate é zero ou ausente, ou o atraso passa do limite configurado. O alerta só sai após N verificações seguidas (padrão 3).

**Reinício.** Automático (por servidor ou por stream, com intervalo mínimo e limite de tentativas por janela; ao atingir o limite gera evento crítico e suspende) ou manual pela tela. Antes de cada reinício a central grava a evidência (JSON bruto, com tokens e senhas mascarados). Cada tentativa, inclusive as que falham, conta no limite. Cerca de 60 s depois verifica se o stream voltou (`restart_ok` / `restart_failed`).
- Endereço de reinício confirmado no Streamer 21.10: `GET /flussonic/api/stream_restart/{nome}`. Para outras versões a central tenta endereços alternativos (`restart_candidates` em `profiles.py`) e lembra o que funcionou por servidor.
- O reinício é a única escrita da central; a leitura é somente-leitura.

**Interface.** Seguem `DESIGN.md`: tema escuro, mobile-first, tabelas viram cartões no celular, diálogo de confirmação antes de reiniciar ou remover.

## Pontos onde a versão aparece

Fonte única: `VERSAO` em `app/version.py`. Espelhada em:
1. Cabeçalho HTTP `X-Greentek-Versao` (todas as respostas).
2. Rodapé da interface (`static/index.html`, marcador `{{VERSAO}}` substituído em `main.py`).
3. `GET /health` (campo `versao`).
4. Título da documentação da API do FastAPI.
5. `CHANGELOG.md` (tabela de versões).

Conferir no ar: `curl -I http://IP_DA_CENTRAL:8000/`.

## Problemas conhecidos

- Só o endereço de reinício do Streamer 21.10 está confirmado em servidor real. Os endereços alternativos para versões novas (ex.: 23.01) são hipótese.
- Unidades de `ts_delay` e `bitrate`, e os campos de estado em `stats` (ex.: `last_dts_at`, `inputs[].active`), ainda não foram confirmados contra um stream travado real. A detecção usa campos assumidos.
- O Dockerfile/docker-compose nunca foram executados; a instalação testada em campo é a do CT com systemd.
- Canais Telegram e e-mail ainda não foram testados contra serviços reais.
- O arquivo `fms_en.pdf` (manual) está no repositório; remover se o repositório for compartilhado.
- O campo "Commit" da última entrada do CHANGELOG só é preenchido no commit seguinte.
