# CHANGELOG

Mais recente no topo. Formato de cada entrada em `REGRAS.md` (seção 2.3).

## Tabela de versões

| Versão | Data | Resumo |
|---|---|---|
| 0.2.2 | 2026-11-07 | Regra 5 do REGRAS.md esclarecida (marca de terceiros só como referência) |
| 0.2.1 | 2026-11-07 | Nome do fabricante volta como referência (não como marca do painel) |
| 0.2.0 | 2026-11-07 | Interface refeita conforme DESIGN.md: tokens Greentek, mobile-first, marca única |
| 0.1.0 | 2026-11-07 | Versão beta inicial: monitoramento, reinício automático/manual, evidências, versão visível |

## [0.2.2] — 2026-11-07
**O que:** regra 5 do `REGRAS.md` reescrita: a marca do painel é só Greentek; nomes de terceiros podem aparecer como referência, nunca como marca do painel.
**Por quê:** pedido do Maicon.
**Arquivos:** `REGRAS.md`, `app/version.py`, `CHANGELOG.md`.
**Como testar:** ler a regra 5; `curl -I http://IP:8000/health` mostra `X-Greentek-Versao: 0.2.2`.
**Commit:** a preencher na próxima entrada.

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
