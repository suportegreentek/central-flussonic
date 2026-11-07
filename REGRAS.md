# PARTE 1 — Regras de trabalho

1. **Confirmar o relato exato antes de agir.** Citar o trecho do pedido do Maicon. Não completar com suposições. Se houver mais de uma leitura possível, perguntar com opções concretas.
2. **O Maicon decide o escopo.** O agente programa. Pedido genérico ou ambíguo: perguntar, não inventar funcionalidade.
3. **Fatos de plataforma só com documentação oficial.** Para Flussonic, buscar e citar a página oficial (flussonic.com/doc). Resumo de busca e fórum não valem como confirmação. Quando só houver fórum, dizer isso.
4. **DESIGN.md é lei.** Toda tela, diálogo e componente novo ou alterado segue o DESIGN.md.
5. **Marca única do painel.** A marca do painel é só "Greentek Soluções Inteligentes" ou "Greentek". Nenhum nome legado. Nomes de terceiros (ex.: Flussonic) podem aparecer como referência ao produto monitorado, nunca como marca do painel.
6. **Relatar com honestidade.** Teste que falhou é dito com a saída do erro. Passo que não foi feito é dito.
7. **Ações difíceis de desfazer ou que afetam servidores em produção** (apagar, sobrescrever, reiniciar serviço, alterar configuração do Flussonic) pedem confirmação antes.
8. **O Maicon está começando em git.** Explicar passos de git de forma simples, sem jargão.

# PARTE 2 — Versionamento e documentação

## 2.1 Versionamento (SemVer: MAJOR.MINOR.PATCH)

- **Todo commit sobe a versão.** MINOR = recurso novo. PATCH = correção. MAJOR = quebra de compatibilidade.
- O projeto começa em **beta `0.1.0`** e fica em `0.x.y` até o Maicon decidir lançar a `1.0.0`.
- A versão tem **uma fonte de verdade** (ex.: constante `VERSAO` no código) e é espelhada onde aparece. Listar esses pontos no DOCUMENTACAO.md e atualizar todos juntos.
- **A versão tem de ser visível no ambiente em produção**: na interface (rodapé) e em um cabeçalho HTTP `X-Greentek-Versao`. Assim se confere o que está no ar com `curl -I`, sem adivinhar.
- O CHANGELOG mantém uma **tabela de versões** (versão, data, resumo).

## 2.2 Toda mudança = 3 coisas

1. Entrada no topo do `CHANGELOG.md`.
2. Atualização do `DOCUMENTACAO.md` onde o comportamento mudou. Item corrigido sai da seção "Problemas conhecidos".
3. `git commit`, com a versão nova.

Documentar faz parte de terminar a tarefa. Não é extra.

## 2.3 Formato da entrada do CHANGELOG (mais recente no topo)

```
## [x.y.z] — AAAA-MM-DD
**O que:** …
**Por quê:** …
**Arquivos:** …
**Como testar:** …
**Commit:** <hash>
```

## 2.4 Arquivos-base do repositório

| Arquivo | Finalidade |
|---|---|
| `REGRAS.md` | Estas regras |
| `DESIGN.md` | Identidade visual e regras de interface |
| `DOCUMENTACAO.md` | Como o sistema funciona, incluindo "Problemas conhecidos" |
| `CHANGELOG.md` | Histórico e tabela de versões |

## 2.5 Documentação nova segue a Norma ATA 100

Estrutura por capítulos, no padrão da especificação da aviação para dados técnicos. **Antes de escrever qualquer documentação nova, perguntar ao Maicon qual o esquema de capítulos**, se ainda não estiver definido aqui. Não se aplica aos arquivos acima enquanto não for decidido.

Esquema de capítulos adotado (numeração `capítulo-seção`, na `DOCUMENTACAO.md`):

| Cap. | Assunto |
|---|---|
| 00 | Geral: finalidade, componentes, convenções |
| 05 | Versionamento e histórico |
| 10 | Instalação e operação |
| 20 | Servidores e credenciais |
| 30 | Monitoramento e detecção |
| 40 | Reinício e evidências |
| 50 | Alertas e notificações |
| 60 | Interface |
| 70 | API e adaptadores por versão |
| 80 | Testes e simulação |
| 90 | Problemas conhecidos |

Assunto novo entra no capítulo que mais combina; capítulo novo só com autorização do Maicon.

# PARTE 3 — Regra para tudo que for web

- **Mobile-first.** Toda interface no navegador é otimizada também para celular e tablet. Desenhar primeiro para tela pequena e expandir.
- Testar em larguras de 360, 768 e 1280 px antes de dar a tarefa como pronta.
- Sem rolagem horizontal da página. Tabelas largas rolam dentro do próprio contêiner ou viram cartões no celular.
- Alvos de toque com no mínimo 44×44 px.
- `<meta name="viewport" content="width=device-width, initial-scale=1">` em toda página.
- Todas as ações disponíveis no desktop precisam existir no celular.
