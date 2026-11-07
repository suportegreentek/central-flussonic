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

**20-1 Cadastro.** Nome (que é o nome do hotel), endereço (protocolo http/https, IP ou nome, e porta em campos separados), autenticação (usuário e senha, token ou nenhuma), tipo de API (automático, v3 ou antiga), cidade, reinício automático e verificação de TLS. Não existe campo "hotel" separado; tags `hotel` de cadastros antigos ficam ocultas.

**20-2 Credenciais.** Criptografadas em repouso (Fernet). A chave vem de `CENTRAL_SECRET_KEY` ou é gerada em `data/secret.key` (permissão 0600). Nunca aparecem em logs, mensagens de erro ou evidências.

**20-2a Endereço separado.** O servidor guarda `scheme` (protocolo), `host` e `port` (porta da API; vazia = padrão do protocolo). A URL base usada nas consultas (`base_url`) é montada a partir deles (`app/endpoint.py`). Bancos antigos são migrados automaticamente ao abrir (a URL antiga é separada). A API ainda aceita `base_url` por compatibilidade.

**20-3 Edição.** Botão Editar na lista de servidores: abre o formulário preenchido. Usuário e senha em branco mantêm os atuais (as credenciais nunca voltam do servidor para a tela). Alterar o endereço, a porta ou o protocolo, ou o tipo de API limpa a versão detectada, que é detectada de novo na próxima coleta.

**20-5 Importação em lote (CSV).** Aba Servidores → "Importar lista de hotéis" (`app/importer.py`, `POST /api/servers/import`).
- Arquivo: planilha salva como CSV (Excel: Salvar como → CSV). Separador vírgula, ponto e vírgula ou tab (detectado); UTF-8 ou Windows-1252 (acentos tratados). Modelo em "Baixar modelo".
- Colunas (cabeçalho obrigatório, ordem livre, sem diferenciar acento/maiúscula): `nome` (ou `hotel`) e `endereco` (IP ou nome; também vale `host`/`ip`) obrigatórias; `porta` e `protocolo` (http/https, padrão http) opcionais; `usuario`, `senha`, `cidade`, `api` (auto, v3, antiga) e `reinicio_automatico` (sim/não) opcionais. A coluna antiga `url` ainda é aceita (é separada em protocolo, endereço e porta); se o endereço vier como `host:porta`, também é separado, e a coluna `porta`, se preenchida, vence.
- Usuário e senha padrão (campos da tela) valem para as linhas que não trazem os seus. Linha sem nenhum dos dois é rejeitada.
- Fluxo em duas etapas: "Verificar arquivo" (nada é gravado; mostra por linha OK, Já existe ou Erro) e depois "Importar N servidores" (com confirmação). Reimportar a mesma lista não duplica: nome ou endereço já cadastrado é ignorado (não atualiza o existente; para isso use Editar).
- Importados entram com reinício automático **desligado** (salvo coluna `reinicio_automatico`) e TLS verificado. Limite: 500 linhas e 1 MB por arquivo.
- A senha nunca volta na resposta da API. O arquivo CSV contém senhas em texto: apagar depois de importar.

**20-4 Usuários do servidor.** Leitura usa o usuário de visualização; o reinício exige usuário com permissão de escrita (`edit_auth`).


**20-6 Acesso SSH (reiniciar serviço ou servidor).** Cada servidor pode ter porta, usuário e senha SSH (formulário de Servidores ou colunas `ssh_porta`, `ssh_usuario`, `ssh_senha` na importação). Em Configurações → "SSH padrão" ficam porta (22), usuário e senha usados pelos servidores sem SSH próprio.
- Regra: usuário **e** senha do servidor sobrescrevem o par padrão; a porta do servidor, se vazia, usa a padrão. Usuário próprio sem senha é recusado.
- Senhas criptografadas (Fernet) no banco; nunca voltam pela API, nem aparecem em eventos, logs ou mensagens de erro. A API só informa se há senha (`has_ssh_password`) e se o SSH está utilizável (`ssh_efetivo`).
- Visão geral, ao abrir um servidor: "Testar SSH", "Reiniciar serviço Flussonic (SSH)" e "Reiniciar servidor (SSH)", sempre com confirmação citando o nome do servidor. Endpoints: `POST /api/servers/{id}/ssh/test|restart-service|reboot`.
- Comandos (`app/ssh.py`): serviço = `systemctl restart flussonic || service flussonic restart`; servidor = `reboot` em segundo plano após 2 s. Usuário diferente de root usa `sudo -S` com a mesma senha (o usuário precisa estar no sudoers).
- Cada ação gera evento `ssh_restart_service` ou `ssh_reboot` (alerta); falha gera `ssh_error` (sem senha). O endereço usado é o do servidor (campo Endereço); a porta SSH é independente da porta da API. Biblioteca: `asyncssh`.

---

## 30 — Monitoramento e detecção

**30-1 Coleta.** Todos os servidores em paralelo, com concorrência e tempo limite por requisição configuráveis. Servidor offline gera evento e não afeta os demais.

**30-2 Critérios de problema.** Estado indicando erro, bitrate zero ou ausente, ou atraso acima do limite configurado.

**30-3 Persistência.** O alerta só sai após N verificações seguidas com problema (padrão 3).

**30-5 Título do stream.** O campo `title` configurado em cada stream no servidor é lido na coleta e gravado junto ao stream. Eventos, evidências e notificações guardam o título vigente no momento (o histórico não muda se o título for alterado depois). Streams sem título aparecem só com o ID. Eventos anteriores à 0.3.0 não têm título.

**30-5a Stream desativado.** Stream marcado como desativado no servidor (campo `disabled` do Flussonic, também em `effective.disabled`) nunca conta como problema: não alerta, não reinicia e aparece com o selo "Desativado". Se ele estava em alerta e foi desativado, o alerta é encerrado sem a mensagem "recuperado". **A forma exata como cada versão do Flussonic informa o desativado ainda não foi confirmada em servidor real** (ver capítulo 90).

**30-6 Ignorar stream.** Para streams com problema persistente já conhecido. Botão "Ignorar" na linha do stream (Visão geral), com motivo opcional (até 200 caracteres). Enquanto ignorado, o stream continua sendo lido e o estado real continua visível, mas:
- não conta como problema (nem no contador do servidor, nem no resumo, nem no filtro "Só com problema");
- não gera alerta nem notificação e não é reiniciado automaticamente (o reinício manual continua disponível);
- aparece com o selo "Ignorado" (azul), o motivo e a contagem "N ignorado(s)" no resumo e no cabeçalho do servidor, para não ser esquecido.
"Voltar a monitorar" desfaz: se o problema ainda persistir, o alerta sai na hora. Ignorar e voltar a monitorar ficam registrados em Eventos (tipos `stream_ignored` e `stream_unignored`, nível info, que não notifica no nível mínimo padrão). Ignorar é por stream; não existe ignorar o servidor inteiro. O reinício automático desligado (aba/coluna "Reinício automático") **não** silencia alertas: é outra configuração.

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

**50-3 Agrupamento (muitos hotéis).** Os alertas de um ciclo de coleta esperam o fim do ciclo e saem agrupados por tipo. Até 3 eventos do mesmo tipo saem como mensagens separadas; acima disso vira **uma** mensagem-resumo, ex.: "20 com problema persistente", agrupada pelo título do stream, com a lista dos hotéis (até 8 por grupo, depois "e mais N"). Assim, uma fonte compartilhada que cai em vários hotéis gera uma mensagem, não dezenas. O histórico (aba Eventos) continua com um registro por stream. Ações manuais saem na hora.

**50-4 Recuperação.** "Stream recuperado" também é avisado (para canais com nível mínimo info ou warning; canais só crítico não recebem). Se o envio falhar, há uma nova tentativa após 2 s e, se falhar de novo, aparece o evento `notify_error` em Eventos.

---

## 60 — Interface

**60-1 Regras.** `DESIGN.md` (tokens Greentek, tema escuro, mobile-first). Verificado em 360, 768 e 1280 px, sem rolagem horizontal.

**60-2 Telas.** Visão geral, Servidores, Eventos, Evidências, Configurações.

**60-3 Visão geral (muitos servidores).** Cada servidor é um cartão **recolhido**: o cabeçalho mostra nome, estado (Online/Offline), o contador "N com problema" ao lado do estado e a quantidade de streams. Clicar no cabeçalho abre a tabela de streams (só os abertos são desenhados). No topo: resumo (online, offline, aguardando coleta, streams com problema) e botões "Expandir os com problema" e "Recolher todos". Ordem: servidores com stream em problema primeiro, depois offline, depois os demais (nome). Servidor offline mostra o motivo sob o cabeçalho. Os cartões abertos são lembrados na sessão do navegador e sobrevivem à atualização automática (15 s). Filtros "Só com problema" e "Estado" escondem servidores sem nada a mostrar, exceto offline.

**60-3a Barra do servidor.** Ao abrir um servidor na Visão geral: "Abrir interface web" (abre `protocolo://endereço:porta/` em outra aba; a senha não vai no link), "Editar servidor" (leva ao formulário já preenchido) e a caixa "Reinício automático dos streams", que liga/desliga na hora, sem sair da Visão geral.

**60-3b Atualização automática sem pulo.** A Visão geral atualiza a cada 15 s. Se nada mudou na tela, ela nem é redesenhada; se mudou, a posição da rolagem e o botão/campo em foco são mantidos. A atualização é adiada enquanto você digita ou escolhe algo num campo, ou enquanto há uma janela de confirmação aberta.

**60-4 Comportamento.** Tabelas viram cartões no celular; status sempre em texto; confirmação antes de reiniciar ou remover; estados de carregando, vazio e erro com mensagem em português.

---

## 70 — API e adaptadores por versão

**70-1 Perfis** (`adapters/profiles.py`): `v3` (`/streamer/api/v3/streams`, paginação por cursor) e `legacy` (`/flussonic/api/media`). Modo automático testa `v3` e cai para `legacy`.

**70-2 Marcação.** Cada item do perfil é marcado `[C]` (confirmado) ou `[H]` (hipótese). Descoberta por servidor: `tools/discover.py` (somente leitura). Resultados em `docs/DISCOVERY.md`.

**70-3 Schema do servidor.** O próprio servidor publica sua descrição em `/streamer/api/v3/schema`. No 21.10 testado, o schema não lista reinício e lista em `stats`: `inputs[]` (`active`, `error`, `bytes`, `last_dts`, `last_dts_at`), `last_dts_at`, `backup_running`, `opened_at`.

---

## 80 — Testes e simulação

**80-1 Testes automáticos.** `.venv/bin/python -m pytest -q` (21 testes: detecção, persistência, limites, reinício por versão, mascaramento, criptografia, versão visível).

**80-1a Isolamento.** `tests/conftest.py` manda o banco e a chave de criptografia dos testes para uma pasta temporária, apagada ao final. Os testes **nunca** tocam em `data/` (o banco de verdade); há um teste que garante isso. Antes da 0.6.0 não era assim: rodar `pytest` dentro de `/opt/central-flussonic` usava o banco real e podia apagar servidores cadastrados.

**80-2 Servidor simulado.** `python tools/fake_flussonic.py --port 9101 --mode v3`. Para simular stream em erro: `curl -X POST 'http://localhost:9101/_sim/ch1?state=error'` (estados: `error`, `lag`, `zero`, `ok`; `&sticky=1` mantém o problema após reiniciar). Cadastrar `http://localhost:9101` na central e acompanhar a aba Eventos.

---

## 90 — Problemas conhecidos

- Só o endereço de reinício do Streamer 21.10 está confirmado em servidor real; os alternativos para versões novas (ex.: 23.01) são hipótese.
- Unidades de `ts_delay` e `bitrate` e os campos de estado em `stats` (ex.: `last_dts_at`, `inputs[].active`) não foram confirmados com um stream travado real; a detecção usa campos assumidos.
- O campo `disabled` (stream desativado) é uma hipótese baseada na configuração do Flussonic; confirmar com o JSON real de um stream desativado.
- Dockerfile e docker-compose nunca foram executados.
- Canais Telegram e e-mail não foram testados contra serviços reais.
- `fms_en.pdf` (manual) está no repositório; remover se o repositório for compartilhado.
- SSH: a identidade (chave) do servidor **não é verificada** (`known_hosts=None`), aceitável em rede interna/VPN; com acesso pela internet, o certo é fixar a chave de cada servidor.
- SSH: o nome do serviço (`flussonic`) e o uso de `sudo` não foram testados em servidores Flussonic reais, só contra um servidor SSH de teste.
- O campo "Commit" da última entrada do CHANGELOG só é preenchido na entrada seguinte.
