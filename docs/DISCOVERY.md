# Etapa de descoberta — status

Fonte usada: manual oficial **fms_en.pdf** (FMS Manual, © Flussonic 2025, seção 2.3.3 "API", págs. 81–88),
que descreve a versão **atual** do Flussonic, **não** a 21.10 nem a 23.01. Os servidores reais ainda não foram consultados.

## Confirmado pelo manual (versão atual)
| Item | Fato |
|---|---|
| Autenticação | HTTP **Basic**. `view_auth` protege leitura; **`edit_auth` protege escrita** (o restart precisa da credencial de `edit_auth`). Bearer também aceito. |
| Listar | `GET /streamer/api/v3/streams` → `{"streams":[…],"next","prev","estimated_count","timing"}` |
| Paginação | `limit=N`; o valor de `next` vai em `cursor=`. Também `select=`, `sort=`, filtros `campo_gt/_lt/...` |
| Detalhe | `GET /streamer/api/v3/streams/{name}`; `/` no nome vira `%2F` |
| Campos | topo: `name`, `static`, `effective.static`, `position`, `named_by`. `stats`: `alive`, `running`, `opened_at` e `start_running_at` (epoch **ms**), `lifetime`, `retry_count`, `input_error_rate`, `bytes_in/out`, `client_count`, `id` |
| Outros campos citados | `stats.bitrate`, `stats.ts_delay` (em sort), `stats.delay` (filtro "delay < 5000") |
| Schema | `GET /streamer/api/v3/schema` devolve o **OpenAPI do próprio servidor** |
| Eventos | `event_sink` pode enviar eventos (`source_connected`, `stream_updated`, ...) por HTTP POST |

## Ainda hipótese
| Item | Hipótese atual no código |
|---|---|
| Endpoint de restart | `POST /streamer/api/v3/streams/{name}/restart`. **Não aparece no manual** (fica na API Reference/schema). |
| Unidade de `ts_delay`/`delay` | milissegundos |
| Unidade de `bitrate` | kbit/s |
| Existe `stats.status`? | O exemplo do manual não mostra. Sem ele, o estado é derivado de `stats.alive`. |
| De onde vem o "error, 4h delay" da UI | provavelmente `alive=false` combinado com `ts_delay` |
| **21.10** | O manual não cobre. A v3 de streams pode não existir; o perfil `legacy` é palpite. |

## Como fechar (por versão: 21.10 e 23.01)
```bash
python tools/discover.py http://IP:8080 --user USER_EDIT_AUTH --password SENHA --out discovery_output/v23 --stream NOME
```
Agora o script baixa `/streamer/api/v3/schema` e imprime os **endpoints de streams (incluindo o restart, se existir)**
e os **campos de stats com descrição e unidade**. É isso que confirma cada [H] em `app/adapters/profiles.py`.
Se possível, rode com `--stream` apontando para um stream que **esteja em erro** naquele momento: isso mostra
qual campo carrega o "4h delay" e testa a hipótese dos timestamps atrasados.
