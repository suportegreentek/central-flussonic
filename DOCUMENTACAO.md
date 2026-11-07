# DOCUMENTAÇÃO — Central de Monitoramento Greentek

Organizada por capítulos numerados (esquema adotado em `REGRAS.md`, seção 2.5). Numeração: `capítulo-seção`.
Versão atual: ver `app/version.py` (capítulo 05).

---

## 00 — Geral

**00-1 Finalidade.** Central web da Greentek que monitora e gerencia, pela API HTTP, os servidores de streaming Flussonic dos hotéis.

**00-2 Componentes** (pasta `app/`):
- `main.py`: servidor web (FastAPI). API em `/api`, interface em `static/index.html`.
- `monitor.py`: coleta periódica, detecção, alertas e reinício.
- `adapters/`: camada por versão do servidor (`base.py`, `profiles.py`).
- `db.py`: banco SQLite. `crypto.py`: criptografia das credenciais. `notify.py`: canais de notificação. `version.py`: versão.

**00-3 Convenções.** Horários guardados em UTC e exibidos em America/Sao_Paulo. Monitoramento somente-leitura; o reinício é a única escrita e é sempre registrado. Textos da interface em português.

---

## 05 — Versionamento e histórico

**05-1 Fonte única.** `VERSAO` em `app/version.py` (SemVer, fase beta `0.x.y`).

**05-2 Pontos onde a versão aparece** (atualizar todos juntos):
1. Cabeçalho HTTP `X-Greentek-Versao` (todas as respostas).
2. Rodapé da interface (`static/index.html`, marcador `{{VERSAO}}` substituído em `main.py`).
3. `GET /health` (campo `versao`).
4. Título da documentação da API do FastAPI.
5. `CHANGELOG.md` (tabela de versões).

**05-3 Conferir no ar.** `curl -I http://IP_DA_CENTRAL:8000/health`.

**05-4 Histórico.** `CHANGELOG.md`.

---

## 10 — Instalação e operação

**10-1 CT Proxmox (modo usado em campo).** No CT, como root:
1. `apt update && apt install -y git python3 python3-venv`
2. `git clone https://github.com/suportegreentek/central-flussonic.git /opt/central-flussonic` e `git checkout greentek`
3. `python3 -m venv .venv` e `.venv/bin/pip install -r requirements.txt` (dentro da pasta)
4. Arquivo `/etc/central-flussonic.env` (permissão 600) com `CENTRAL_ADMIN_USER`, `CENTRAL_ADMIN_PASSWORD` e `CENTRAL_DATA_DIR=/opt/central-flussonic/data`.
5. Serviço systemd `/etc/systemd/system/central-flussonic.service` executando `uvicorn app.main:app --host 0.0.0.0 --port 8000`, com `Restart=always`, e `systemctl enable --now central-flussonic`.

**10-2 Atualizar.** `cd /opt/central-flussonic && git pull && systemctl restart central-flussonic`.

**10-3 Docker.** `Dockerfile` e `docker-compose.yml` (exige `CENTRAL_ADMIN_PASSWORD`; dados em `./data`). Não testado em campo (ver capítulo 90).

**10-4 Variáveis.** `CENTRAL_DATA_DIR`, `CENTRAL_DB`, `CENTRAL_SECRET_KEY`, `CENTRAL_ADMIN_USER`, `CENTRAL_ADMIN_PASSWORD` (`app/config.py`).

**10-5 Segurança.** Usar senha forte e não expor a porta 8000 à internet.

---

## 20 — Servidores e credenciais

**20-1 Cadastro.** Nome, endereço (URL), autenticação (usuário e senha, token ou nenhuma), tipo de API (automático, v3 ou antiga), tags (hotel, cidade), reinício automático e verificação de TLS.

**20-2 Credenciais.** Criptografadas em repouso (Fernet). A chave vem de `CENTRAL_SECRET_KEY` ou é gerada em `data/secret.key` (permissão 0600). Nunca aparecem em logs, mensagens de erro ou evidências.

**20-3 Edição.** Botão Editar na lista de servidores: abre o formulário preenchido. Usuário e senha em branco mantêm os atuais (as credenciais nunca voltam do servidor para a tela). Alterar a URL ou o tipo de API limpa a versão detectada, que é detectada de novo na próxima coleta.

**20-4 Usuários do servidor.** Leitura usa o usuário de visualização; o reinício exige usuário com permissão de escrita (`edit_auth`).

---

## 30 — Monitoramento e detecção

**30-1 Coleta.** Todos os servidores em paralelo, com concorrência e tempo limite por requisição configuráveis. Servidor offline gera evento e não afeta os demais.

**30-2 Critérios de problema.** Estado indicando erro, bitrate zero ou ausente, ou atraso acima do limite configurado.

**30-3 Persistência.** O alerta só sai após N verificações seguidas com problema (padrão 3).

**30-5 Título do stream.** O campo `title` configurado em cada stream no servidor é lido na coleta e gravado junto ao stream. Eventos, evidências e notificações guardam o título vigente no momento (o histórico não muda se o título for alterado depois). Streams sem título aparecem só com o ID. Eventos anteriores à 0.3.0 não têm título.

**30-4 Parâmetros** (aba Configurações): intervalo de coleta, tempo limite, servidores em paralelo, atraso máximo, verificações seguidas, intervalo mínimo entre reinícios, reinícios por janela, janela, verificação após reinício. Valores-padrão em `app/config.py`.

---

## 40 — Reinício e evidências

**40-1 Modos.** Automático (por servidor ou por stream) e manual pela tela, com diálogo de confirmação.

**40-2 Limites.** Intervalo mínimo entre reinícios e máximo de tentativas por janela. Cada tentativa, inclusive as que falham, conta. Ao atingir o limite: evento crítico `restart_limit` e suspensão para aquele stream.

**40-3 Evidência.** Antes de cada reinício grava-se o JSON bruto do stream (aba Evidências), com tokens, senhas e credenciais em URLs mascarados.

**40-4 Verificação.** Cerca de 60 s depois verifica-se o stream: evento `restart_ok` ou `restart_failed`.

**40-5 Endereço de reinício.** Confirmado no Streamer 21.10: `GET /flussonic/api/stream_restart/{nome}` (responde 200 `true`). Para outras versões a central tenta os endereços de `restart_candidates` (`profiles.py`) em ordem, avançando só em 404/405, e lembra o que funcionou por servidor. O endereço usado aparece nos detalhes do evento de reinício.

---

## 50 — Alertas e notificações

**50-1 Eventos.** Nível info, alerta ou crítico, gravados no histórico (aba Eventos, com filtros por servidor, stream, nível e tipo).

**50-2 Canais.** Webhook, Telegram e e-mail, com nível mínimo por canal, ativar/desativar e botão de teste. Botão Editar: nome, nível mínimo e estado; a configuração (JSON) é opcional e, se informada, só os campos enviados mudam (ex.: trocar apenas `chat_id`, sem reenviar o token). O tipo do canal não muda (remova e crie outro). O teste do Telegram mostra o motivo da recusa, sem o token. Mensagens de notificação incluem o título do stream. A configuração do canal nunca vai para logs. Novos tipos entram em `CHANNEL_TYPES` (`notify.py`).

---

## 60 — Interface

**60-1 Regras.** `DESIGN.md` (tokens Greentek, tema escuro, mobile-first). Verificado em 360, 768 e 1280 px, sem rolagem horizontal.

**60-2 Telas.** Visão geral, Servidores, Eventos, Evidências, Configurações.

**60-3 Comportamento.** Tabelas viram cartões no celular; status sempre em texto; confirmação antes de reiniciar ou remover; estados de carregando, vazio e erro com mensagem em português.

---

## 70 — API e adaptadores por versão

**70-1 Perfis** (`adapters/profiles.py`): `v3` (`/streamer/api/v3/streams`, paginação por cursor) e `legacy` (`/flussonic/api/media`). Modo automático testa `v3` e cai para `legacy`.

**70-2 Marcação.** Cada item do perfil é marcado `[C]` (confirmado) ou `[H]` (hipótese). Descoberta por servidor: `tools/discover.py` (somente leitura). Resultados em `docs/DISCOVERY.md`.

**70-3 Schema do servidor.** O próprio servidor publica sua descrição em `/streamer/api/v3/schema`. No 21.10 testado, o schema não lista reinício e lista em `stats`: `inputs[]` (`active`, `error`, `bytes`, `last_dts`, `last_dts_at`), `last_dts_at`, `backup_running`, `opened_at`.

---

## 80 — Testes e simulação

**80-1 Testes automáticos.** `.venv/bin/python -m pytest -q` (10 testes: detecção, persistência, limites, reinício por versão, mascaramento, criptografia, versão visível).

**80-2 Servidor simulado.** `python tools/fake_flussonic.py --port 9101 --mode v3`. Para simular stream em erro: `curl -X POST 'http://localhost:9101/_sim/ch1?state=error'` (estados: `error`, `lag`, `zero`, `ok`; `&sticky=1` mantém o problema após reiniciar). Cadastrar `http://localhost:9101` na central e acompanhar a aba Eventos.

---

## 90 — Problemas conhecidos

- Só o endereço de reinício do Streamer 21.10 está confirmado em servidor real; os alternativos para versões novas (ex.: 23.01) são hipótese.
- Unidades de `ts_delay` e `bitrate` e os campos de estado em `stats` (ex.: `last_dts_at`, `inputs[].active`) não foram confirmados com um stream travado real; a detecção usa campos assumidos.
- Dockerfile e docker-compose nunca foram executados.
- Canais Telegram e e-mail não foram testados contra serviços reais.
- `fms_en.pdf` (manual) está no repositório; remover se o repositório for compartilhado.
- O campo "Commit" da última entrada do CHANGELOG só é preenchido na entrada seguinte.
