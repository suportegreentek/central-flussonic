# Etapa de descoberta — status

**Não concluída com dados reais.** Esta sessão não alcança os servidores Flussonic nem o site de documentação
(`flussonic.com` não resolve no ambiente). Portanto os endpoints/campos em `app/adapters/profiles.py` são
**hipóteses a confirmar**, não fatos:

| Item | Hipótese (não verificada) |
|---|---|
| 23.01 lista | `GET /streamer/api/v3/streams` → `{"streams":[…], "next":…}` |
| 23.01 detalhe | `GET /streamer/api/v3/streams/{name}` |
| 23.01 restart | `POST /streamer/api/v3/streams/{name}/restart` |
| 21.10 | pode **não** ter a v3 (uma busca sugere que a v3 de streams veio na 21.11). Candidatos: `/flussonic/api/media`, `/flussonic/api/stream_restart/{name}` |
| Auth | HTTP Basic (usuário/senha da API); Bearer disponível |
| Campos | `stats.status`, `stats.input_bitrate`/`bitrate` (kbit/s?), `stats.lag_ms`/`lag`, `stats.opened_at` (ms?) |

## Como concluir (10 min por versão)
```bash
python tools/discover.py http://IP_23_01:8080 --user U --password P --out discovery_output/v23 --stream NOME_DE_UM_STREAM
python tools/discover.py http://IP_21_10:8080 --user U --password P --out discovery_output/v21
```
O script só faz GET, salva o JSON bruto de cada endpoint e imprime quais responderam e as chaves de `stats`.
Com isso: (1) ajuste `profiles.py` (caminhos, `*_keys`, unidade do atraso), (2) confirme que o
restart é o endpoint certo, (3) se possível capture um stream **em erro** para validar qual campo carrega o "4h delay".
Use "Testar" na tela de Servidores para ver o perfil detectado.
