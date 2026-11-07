# CHANGELOG

Mais recente no topo. Formato de cada entrada em `REGRAS.md` (seção 2.3).

## Tabela de versões

| Versão | Data | Resumo |
|---|---|---|
| 0.6.0 | 2026-11-07 | Ignorar stream com problema conhecido (sem contagem, alerta ou reinício) |
| 0.5.0 | 2026-11-07 | Visão geral com servidores recolhidos e contador de problemas |
| 0.4.0 | 2026-11-07 | Importação de hotéis por CSV; campo Hotel removido (nome = hotel) |
| 0.3.0 | 2026-11-07 | Editar servidores e canais; título do stream em eventos, evidências e notificações |
| 0.2.5 | 2026-11-07 | Telegram: erro do teste mostra o motivo; assunto do e-mail com marca Greentek |
| 0.2.4 | 2026-11-07 | Correção: `app/version.py` tinha sido gravado vazio na 0.2.3 |
| 0.2.3 | 2026-11-07 | Documentação reorganizada no esquema de capítulos (ATA 100 adaptado) |
| 0.2.2 | 2026-11-07 | Regra 5 do REGRAS.md esclarecida (marca de terceiros só como referência) |
| 0.2.1 | 2026-11-07 | Nome do fabricante volta como referência (não como marca do painel) |
| 0.2.0 | 2026-11-07 | Interface refeita conforme DESIGN.md: tokens Greentek, mobile-first, marca única |
| 0.1.0 | 2026-11-07 | Versão beta inicial: monitoramento, reinício automático/manual, evidências, versão visível |

## [0.6.1] — 2026-11-07
**O que:** quando o envio de um alerta falha (Telegram fora do ar, limite de envios, rede), a central tenta de novo uma vez após 2 s e, se falhar, registra o evento `notify_error` em Eventos, com o canal e o motivo.
**Por quê:** um stream foi reiniciado e nenhum alerta chegou ao Telegram. O erro de envio só ia para o log do serviço e o alerta sumia sem rastro na tela.
**Arquivos:** `app/notify.py`, `tests/test_monitor.py`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** `python -m pytest -q` (22 testes); `curl -I http://IP:8000/health` mostra `X-Greentek-Versao: 0.6.1`.
**Commit:** a preencher na próxima entrada

## [0.6.0] — 2026-11-07
**O que:** botão "Ignorar" por stream, com motivo opcional. Stream ignorado continua sendo lido, mas não conta como problema, não alerta/notifica e não é reiniciado automaticamente; aparece com selo "Ignorado", motivo e contador "N ignorado(s)". "Voltar a monitorar" desfaz (alerta volta na hora se o problema persistir). Ações registradas em Eventos. Banco migrado automaticamente (colunas `ignored`, `ignore_note`, `ignored_at`). **Correção de segurança dos testes:** `tests/conftest.py` isola os testes em banco temporário; antes eles usavam `./data/central.db` (o banco real quando rodados no CT) e alguns testes novos apagam servidores.
**Por quê:** pedido do Maicon: streams com problema persistente, a resolver depois, não devem avisar à toa nem aparecer como erro.
**Arquivos:** `app/db.py`, `app/monitor.py`, `app/main.py`, `static/index.html`, `tests/test_monitor.py`, `tests/conftest.py`, `DOCUMENTACAO.md`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** `python -m pytest -q` (21 passam); Visão geral → Ignorar num stream em erro: o contador de problemas cai, aparece "1 ignorado(s)" e o reinício automático para.
**Commit:** efe2cc9.

## [0.5.0] — 2026-11-07
**O que:** Visão geral reformulada para muitos servidores: cada servidor vem recolhido, com o contador "N com problema" ao lado do estado Online; resumo no topo (online, offline, aguardando, streams com problema); botões "Expandir os com problema" e "Recolher todos"; servidores com problema aparecem primeiro, depois os offline; estado dos cartões lembrado ao atualizar. Só os cartões abertos são desenhados (tela leve com 75+ servidores).
**Por quê:** pedido do Maicon: com mais de 75 servidores a tela ficava difícil de visualizar.
**Arquivos:** `static/index.html`, `DOCUMENTACAO.md`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** abrir a Visão geral com vários servidores e conferir em 360, 768 e 1280 px; `curl -I http://IP:8000/health` mostra `X-Greentek-Versao: 0.5.0`.
**Commit:** 9baccc2

## [0.4.0] — 2026-11-07
**O que:** (1) importação em lote de servidores por planilha CSV, com verificação prévia por linha, modelo para baixar, usuário/senha padrão e proteção contra duplicados; (2) removido o campo "Hotel" do formulário, porque o nome já é o hotel (tags `hotel` antigas ficam ocultas).
**Por quê:** pedido do Maicon: cadastrar mais de 75 hotéis sem digitar um a um.
**Arquivos:** `app/importer.py`, `app/main.py`, `static/index.html`, `tests/test_monitor.py`, `DOCUMENTACAO.md`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** `python -m pytest -q` (18 passam); Servidores → Baixar modelo → preencher → Verificar arquivo → Importar.
**Commit:** 0e86ff7

## [0.3.0] — 2026-11-07
**O que:** (1) botão Editar em servidores e em canais de notificação (antes só incluir/remover); canais ganham ativar/desativar e edição parcial da configuração sem expor o token. (2) o título do stream (campo `title` do servidor) passa a aparecer em Eventos, Evidências, Visão geral, no diálogo de reinício e nas mensagens de notificação. Banco migrado automaticamente (colunas novas).
**Por quê:** pedido do Maicon: identificar o stream pelo nome e corrigir cadastros sem apagar e recriar.
**Arquivos:** `app/main.py`, `app/db.py`, `app/monitor.py`, `app/notify.py`, `app/adapters/base.py`, `static/index.html`, `tools/fake_flussonic.py`, `tests/test_monitor.py`, `DOCUMENTACAO.md`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** `python -m pytest -q` (16 passam); na tela, Servidores → Editar; Configurações → Editar canal; aba Eventos mostra o título abaixo do ID.
**Commit:** 18fd994

## [0.2.5] — 2026-11-07
**O que:** quando o Telegram recusa a mensagem, o teste do canal mostra o motivo informado por ele (ex.: "bot is not a member of the channel chat") em vez de só "HTTPStatusError". O token nunca aparece na mensagem. Assunto do e-mail trocado de "[Flussonic]" para "[Greentek]".
**Por quê:** configurar o bot `greentek_bot` para o canal `@greentek_notifica` e facilitar achar o erro; marca do painel só Greentek.
**Arquivos:** `app/notify.py`, `tests/test_monitor.py`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** `python -m pytest -q` (11 passam); na aba Configurações, "Testar" no canal.
**Commit:** 4eaa35c

## [0.2.4] — 2026-11-07
**O que:** corrigido `app/version.py`, que ficou vazio na 0.2.3 e impedia a central de iniciar.
**Por quê:** erro meu ao subir a versão (o arquivo foi aberto para escrita antes de ser lido) e o envio seguiu mesmo com um teste falhando.
**Arquivos:** `app/version.py`, `CHANGELOG.md`.
**Como testar:** `python -m pytest -q` (10 passam); `curl -I http://IP:8000/health` mostra `X-Greentek-Versao: 0.2.4`.
**Commit:** 69ac0a4

## [0.2.3] — 2026-11-07
**O que:** `DOCUMENTACAO.md` reorganizada em capítulos numerados (00 a 90); esquema registrado no `REGRAS.md` (seção 2.5). Acrescentados instalação no CT, atualização, simulação de stream em erro e referência de parâmetros.
**Por quê:** esquema de capítulos aprovado pelo Maicon.
**Arquivos:** `DOCUMENTACAO.md`, `REGRAS.md`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** abrir `DOCUMENTACAO.md` e conferir os capítulos; `curl -I http://IP:8000/health` mostra `X-Greentek-Versao: 0.2.3`.
**Commit:** 5b1cb71 (versão quebrada, corrigida na 0.2.4)

## [0.2.2] — 2026-11-07
**O que:** regra 5 do `REGRAS.md` reescrita: a marca do painel é só Greentek; nomes de terceiros podem aparecer como referência, nunca como marca do painel.
**Por quê:** pedido do Maicon.
**Arquivos:** `REGRAS.md`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** ler a regra 5; `curl -I http://IP:8000/health` mostra `X-Greentek-Versao: 0.2.2`.
**Commit:** 3f7d2e9

## [0.2.1] — 2026-11-07
**O que:** o nome "Flussonic" volta a aparecer na interface apenas como referência ao produto monitorado (formulário de servidor, texto das evidências, estado vazio). A marca do painel continua só Greentek.
**Por quê:** esclarecimento do Maicon sobre a regra 5: marca de terceiros pode aparecer, mas não como se fosse do painel.
**Arquivos:** `static/index.html`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** abrir Servidores e Evidências e conferir os textos; `curl -I http://IP:8000/health` mostra `X-Greentek-Versao: 0.2.1`.
**Commit:** 22969e5

## [0.2.0] — 2026-11-07
**O que:** interface refeita seguindo o `DESIGN.md`: tema escuro com tokens Greentek, layout mobile-first (tabelas viram cartões no celular), alvos de toque de 44 px, foco visível, estados de carregando/vazio/erro, diálogos de confirmação com o nome do servidor/stream, status com texto e ícone (nunca só cor), valores técnicos em fonte monoespaçada. Nome de terceiros removido da interface.
**Por quê:** regras 4 e 5 do `REGRAS.md` e Parte 3 (web mobile-first).
**Arquivos:** `static/index.html`, `DOCUMENTACAO.md`, `CHANGELOG.md`, `app/version.py`.
**Como testar:** abrir a central em 360, 768 e 1280 px; conferir ausência de rolagem horizontal; `curl -I http://IP:8000/` mostra `X-Greentek-Versao: 0.2.0`.
**Commit:** f9653c4

## [0.1.0] — 2026-11-07
**O que:** versão beta inicial da central: cadastro de servidores (credenciais criptografadas), visão geral com filtros, monitoramento periódico com concorrência e timeout, detecção de stream com problema (status de erro, bitrate zero/ausente ou atraso acima do limite, por N verificações seguidas), alertas e canais (webhook, Telegram, e-mail), reinício automático com intervalo mínimo e limite por janela, reinício manual, evidência (JSON bruto) antes de cada reinício, histórico de eventos. Reinício confirmado no Streamer 21.10 (`GET /flussonic/api/stream_restart/{nome}`) com endereços alternativos para outras versões. Tokens e senhas mascarados nas evidências. Tentativas de reinício que falham contam no limite. Versão visível no rodapé, em `/health` e no cabeçalho `X-Greentek-Versao`.
**Por quê:** monitorar e reiniciar streams travados dos servidores dos hotéis.
**Arquivos:** `app/`, `static/index.html`, `tools/`, `tests/`, `docs/DISCOVERY.md`, `REGRAS.md`, `DESIGN.md`.
**Como testar:** `python -m pytest -q` (10 testes); `curl -I http://IP:8000/health` mostra `X-Greentek-Versao: 0.1.0`.
**Commit:** 6de38d6
