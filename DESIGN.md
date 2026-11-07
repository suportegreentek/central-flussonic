# DESIGN.md — base visual Greentek

> **Status:** especificação viva. Base de marca para qualquer produto web da Greentek.
> Derivada do design system do app de TV, sem nada específico de TV.

## 4.0 Direção

Interface **sóbria, técnica e confiável**. Superfícies grafite escuras, verde Greentek como sinal funcional, laranja como acento secundário, tipografia branca forte, geometria simples, bordas sutis, movimento discreto.

**Nunca** deve parecer: cyberpunk, gamer, neon, cripto, painel "feito por IA", glassmorphism, 3D, degradê chamativo. Nada de brilho (glow) nem sombras coloridas.

Na dúvida, escolher o tratamento mais simples e mais legível.

## 4.1 Princípios

1. **Verde é sinal.** Significa ativo, selecionado, acionável ou confirmado. Não espalhar verde pela tela.
2. **Informação antes de decoração.** Cada elemento precisa ter função.
3. **Hierarquia por contraste e tamanho**, não por cor.
4. **Consistência.** Mesmo componente, mesma aparência, em todas as telas.
5. **Estado sempre visível.** Carregando, vazio, erro e sucesso têm tratamento próprio.

## 4.2 Cores (tokens oficiais)

| Token | Valor | Uso |
|---|---|---|
| Verde 500 | `#A3D168` | Ação primária, ativo, foco |
| Laranja 500 | `#F58020` | Acento secundário, ênfase especial |
| Preto 900 | `#1C1C1C` | Base escura da marca |
| Branco | `#FFFFFF` | Texto principal |
| Cinza 050 | `#F4F4F4` | Superfície clara, se necessário |

```css
:root {
  --color-brand-green-400: #B7E27F;
  --color-brand-green-500: #A3D168;
  --color-brand-green-600: #89B84B;
  --color-brand-green-700: #6F9839;

  --color-brand-orange-400: #FF9A48;
  --color-brand-orange-500: #F58020;
  --color-brand-orange-600: #D9650A;

  --color-neutral-000: #FFFFFF;
  --color-neutral-050: #F4F4F4;
  --color-neutral-100: #E7E7E7;
  --color-neutral-200: #C9C9C9;
  --color-neutral-300: #A8A8A8;
  --color-neutral-500: #6F6F6F;
  --color-neutral-700: #363636;
  --color-neutral-800: #272727;
  --color-neutral-900: #1C1C1C;
  --color-neutral-950: #101010;

  --color-danger-500:  #E15B64;
  --color-warning-500: #E5B84B;
  --color-success-500: #7FBF45;
  --color-info-500:    #6AA7C8;

  /* semânticos (tema escuro, padrão) */
  --bg-app:        var(--color-neutral-950);
  --bg-surface:    var(--color-neutral-900);
  --bg-surface-2:  var(--color-neutral-800);
  --border:        var(--color-neutral-700);
  --border-focus:  var(--color-brand-green-500);
  --text-primary:   #FFFFFF;
  --text-secondary: #D0D0D0;
  --text-tertiary:  #A8A8A8;
  --text-disabled:  #6A6A6A;
}
```

Regras de uso:
- Fundo da página `--bg-app`; cartões e painéis `--bg-surface`; elementos elevados `--bg-surface-2`. Evitar preto puro em tudo.
- Botão primário: fundo verde 500 com texto `--color-neutral-900`. Secundário: contorno cinza, sem preenchimento. Laranja só para ênfase pontual.
- Estados de status: **sucesso**, **alerta**, **erro** e **informação** usam os tokens de status, sempre acompanhados de ícone ou texto. Nunca só cor.
- Tema claro é opcional. Se existir, usar `--color-neutral-050` como fundo e **verificar o contraste do verde sobre claro** antes de usar como texto (verde 500 sobre branco não passa em contraste).

## 4.3 Acessibilidade e contraste

- Texto normal: contraste mínimo **4.5:1**. Texto grande e componentes de interface: **3:1** (WCAG 2.1 AA).
- Foco por teclado sempre visível: contorno de 2 px em `--border-focus`.
- Nunca transmitir informação só por cor.
- Respeitar `prefers-reduced-motion`.

## 4.4 Tipografia

- Fonte de sistema sem serifa (a definir com o Maicon se houver fonte da marca). Uma família só.
- Escala sugerida: 12 / 14 / 16 / 20 / 24 / 32 px. Corpo mínimo de 16 px no celular.
- Pesos: 400 corpo, 600 títulos e rótulos. Texto em maiúsculas só para rótulos curtos.
- Números e valores técnicos (IPs, portas, bitrates) em fonte monoespaçada.

## 4.5 Layout e responsividade (mobile-first)

- Grade de 4 pt (espaçamentos 4, 8, 12, 16, 24, 32, 48).
- Pontos de quebra: **base** (até 767 px), **tablet** (768 px), **desktop** (1024 px), **largo** (1440 px).
- Celular: coluna única, navegação recolhida em menu, ações principais ao alcance do polegar.
- Desktop: navegação lateral fixa, conteúdo em até 12 colunas.
- Tabelas: no celular viram lista de cartões ou rolam dentro do contêiner, nunca estouram a página.
- Formulários: um campo por linha no celular, rótulo sempre visível (não só placeholder), teclado correto (`type`, `inputmode`).
- Alvos de toque mínimo 44×44 px, com espaço entre eles.
- Testar em 360, 768 e 1280 px.

## 4.6 Forma, elevação e movimento

- Raios pequenos e consistentes (4 a 8 px). Bordas de 1 px em `--border`.
- Elevação por camada de cor, não por sombra. Se houver sombra, neutra e discreta.
- Movimento de 120 a 200 ms, curva suave, só para dar feedback. Sem animação decorativa.

## 4.7 Componentes

- Todo componente define: estados padrão, foco, ativo, desabilitado, carregando, erro.
- Diálogos de confirmação para ações destrutivas, com texto claro do que será afetado (ex.: nome do servidor ou stream).
- **Estados vazios, de carregamento, offline e de erro** têm mensagem em português, curta, dizendo o que aconteceu e o que fazer.
- Ícones: um único conjunto de traço simples, tamanho consistente.

## 4.8 Regras para agentes de IA

1. Usar só os tokens acima. Não criar cores novas sem perguntar ao Maicon.
2. Não adicionar degradês, brilho, glassmorphism, ilustrações genéricas ou emojis decorativos.
3. Toda tela nova precisa ser conferida em 360, 768 e 1280 px.
4. Em dúvida visual, perguntar com opções concretas.

## 4.9 Checklist de QA de tela

- [ ] Usa só tokens do DESIGN.md
- [ ] Verde só em ação, foco ou estado ativo
- [ ] Contraste de texto ≥ 4.5:1
- [ ] Foco por teclado visível
- [ ] Sem rolagem horizontal em 360 px
- [ ] Alvos de toque ≥ 44 px
- [ ] Estados vazio, carregando, erro e sucesso tratados
- [ ] Textos em português, sem nome legado
- [ ] Versão visível; CHANGELOG, DOCUMENTACAO e commit feitos
