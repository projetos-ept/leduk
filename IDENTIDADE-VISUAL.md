# LeDuk — Identidade Visual e Design System

Referência para implementação de novas telas. Qualquer componente novo deve usar estas variáveis, classes e padrões antes de inventar estilo próprio.

---

## 1. Paleta de cores

Todas as cores vivem em `:root` em `static/css/base.css`.

| Variável CSS | Hex padrão | Uso |
|---|---|---|
| `--primaria` / `--accent` | `#5b8dee` | Ações primárias, links, badges de número |
| `--sucesso` | `#00c9a7` | Confirmação, notas aprovadas, toggle ativa |
| `--erro` | `#ff6b6b` | Erros de validação |
| `--aviso` | `#f7b731` | Alertas, notas pendentes |
| `--fundo` / `--bg` | `#f0f4ff` | Background geral da página |
| `--card` / `--surface` | `#ffffff` | Background de cards e modais |
| `--texto` / `--text` | `#2d3748` | Texto de corpo principal |
| `--suave` / `--muted` | `#718096` | Texto secundário, placeholders, labels |
| `--borda` / `--border` | `#e2e8f0` | Bordas de cards, separadores |
| `--raio` | `14px` | Border-radius padrão de cards |
| `--sombra` | `0 4px 20px rgba(91,141,238,.10)` | Sombra padrão de cards |

### Variante de tema (disciplina)

O background da página de atividade do aluno pode receber `data-tema="hematologia"` etc., que sobrescreve `--primaria`. Não usar em telas do professor.

### Cores de badge por tipo de questão

| Tipo | Background | Texto |
|---|---|---|
| MC4 | `#dbeafe` | `#1d4ed8` |
| MC5 | `#e0e7ff` | `#3730a3` |
| VF  | `#d1fae5` | `#065f46` |
| ABERTA | `#fef3c7` | `#92400e` |
| ASSOCIATIVA | `#fce7f3` | `#9d174d` |

---

## 2. Tipografia

```css
--sans: 'Segoe UI', system-ui, -apple-system, sans-serif;
/* monospace: font-family: monospace (para labels técnicos, badges de peso, código) */
```

| Contexto | Tamanho | Peso | Variável |
|---|---|---|---|
| Título de página (H1) | `1.3–1.4rem` | `800` | `--text` |
| Título de card | `1.05rem` | `700` | `--text` |
| Corpo principal | `0.9rem` | `400` | `--text` |
| Label de campo | `0.85rem` | `600` | `--text` |
| Texto secundário / muted | `0.8–0.85rem` | `400` | `--muted` |
| Badge / tag | `0.7–0.75rem` | `700` | varia |
| Rótulo mono (peso, código) | `0.72rem` | `700` | `font-family: monospace` |

---

## 3. Componentes

### 3.1 Card

```html
<div class="card">
  <!-- conteúdo -->
</div>
```

**Variante elevada (questão, atividade):**
```html
<div class="qb-card">...</div>
```
CSS: `background: var(--card); border: 1px solid var(--borda); border-radius: 14px; padding: 16px 18px; box-shadow: 0 1px 4px rgba(0,0,0,.04);`  
Hover: `box-shadow: 0 4px 16px rgba(91,141,238,.12);`

**Card de stat (número grande + label):**
```html
<div class="qb-stat-card">
  <span class="qb-stat-num">42</span>
  <span class="qb-stat-label">questões</span>
</div>
<!-- variante com destaque: qb-stat-card qb-stat-card--accent -->
```

---

### 3.2 Botões

Três variantes. Todas usam `display: inline-flex; align-items: center; gap: 6px;`.

| Classe | Aparência | Quando usar |
|---|---|---|
| `.btn-primary` | Fundo `--primaria`, texto branco | Ação principal da tela (Nova questão, Salvar) |
| `.btn-ghost` | Fundo transparente, borda `--borda`, hover azul | Ações secundárias (Editar, Voltar, Clonar) |
| `.btn-danger` | Borda vermelha fraca, texto vermelho; hover fundo vermelho | Ações destrutivas (Excluir) |

**Modificador de tamanho:**
```html
<button class="btn-primary btn-sm">Ação</button>
```
`.btn-sm`: `padding: 7px 12px; font-size: .8rem; border-radius: 8px;`

**Botão ícone (link copy):**
```html
<button class="btn-ghost btn-sm btn-icon-only" title="Copiar link">🔗</button>
```

**Exemplos:**
```html
<a href="/..." class="btn-primary">+ Nova questão</a>
<a href="/..." class="btn-ghost btn-sm">Editar</a>
<button type="button" class="btn-danger btn-sm" onclick="...">Excluir</button>
```

---

### 3.3 Badge de tipo de questão

```html
<span class="quest-tipo-badge quest-tipo-mc4">MC4</span>
<span class="quest-tipo-badge quest-tipo-vf">VF</span>
<span class="quest-tipo-badge quest-tipo-aberta">ABERTA</span>
```

---

### 3.4 Badge de nota

```html
<span class="nota-badge nota-verde">9.5</span>
<span class="nota-badge nota-amarelo">5.0</span>
<span class="nota-badge nota-vermelho">2.0</span>
<span class="nota-badge nota-pendente">—</span>
<span class="nota-badge nota-liberada">Liberada</span>
```

---

### 3.5 Toggle de status (HTMX)

```html
<!-- componente em templates/components/_toggle_ativa.html -->
<!-- requer ativ_id e ativa no contexto Jinja -->
{% set ativ_id = ativ.id %}
{% set ativa = ativ.ativa %}
{% include "components/_toggle_ativa.html" with context %}
```

---

### 3.6 Breadcrumb

```html
<div class="breadcrumb">
  <a href="/professor/dashboard">Dashboard</a>
  <span>›</span>
  <a href="/professor/turma/{{ turma.id }}">{{ turma.nome }}</a>
  <span>›</span>
  <span>Questões</span>  <!-- último item: só texto, sem link -->
</div>
```

---

### 3.7 Estado vazio

```html
<div class="qb-empty">
  <p class="dash-empty-icon">📝</p>   <!-- emoji representativo -->
  <p class="qb-empty-msg">Nenhuma questão cadastrada nesta atividade.</p>
  <a href="/..." class="btn-primary">+ Criar primeira questão</a>
</div>
```

---

### 3.8 Modal de confirmação

Substitui `window.confirm()`. Acessível: fecha com Escape e clique no overlay.

```html
<div id="modal-excluir" class="modal-overlay" role="dialog" aria-modal="true"
     aria-labelledby="modal-titulo" hidden>
  <div class="modal-box">
    <h2 class="modal-titulo" id="modal-titulo">Excluir item</h2>
    <p class="modal-msg">Confirma a exclusão de <strong id="modal-item-nome"></strong>?</p>
    <div class="modal-acoes">
      <button type="button" class="btn-ghost" onclick="fecharModal()">Cancelar</button>
      <form id="form-excluir" method="post" style="display:inline;">
        <button type="submit" class="btn-danger">Excluir</button>
      </form>
    </div>
  </div>
</div>

<script>
function abrirModal(itemId, nome) {
  document.getElementById('form-excluir').action = '/rota/' + itemId + '/excluir';
  document.getElementById('modal-item-nome').textContent = nome;
  const m = document.getElementById('modal-excluir');
  m.hidden = false;
  m.querySelector('.btn-ghost').focus();
}
function fecharModal() {
  document.getElementById('modal-excluir').hidden = true;
}
document.getElementById('modal-excluir').addEventListener('click', e => {
  if (e.target === e.currentTarget) fecharModal();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') fecharModal(); });
</script>
```

---

### 3.9 Toast de cópia de link

```html
<div id="toast-link" class="toast-copy" aria-live="polite"></div>

<script>
function copiarLink(btn, id) {
  const url = window.location.origin + '/atividade/' + id;
  navigator.clipboard.writeText(url).then(() => {
    const t = document.getElementById('toast-link');
    t.textContent = 'Link copiado!';
    t.classList.add('toast-visible');
    setTimeout(() => t.classList.remove('toast-visible'), 2000);
  });
}
</script>
```

---

### 3.10 Mapa de calor (heatmap de notas)

```html
<div style="overflow-x:auto;">
  <table class="mapa-calor">
    <thead>
      <tr>
        <th class="mapa-nome">Aluno</th>
        <th title="Nome completo da atividade">Ativ abreviada…</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="mapa-nome">João Silva</td>
        <td class="mapa-verde">92%</td>
        <td class="mapa-amarelo">55%</td>
        <td class="mapa-vermelho">28%</td>
        <td class="mapa-vazio">—</td>
      </tr>
    </tbody>
  </table>
</div>
```

Limiares: `>= 70%` → verde · `>= 40%` → amarelo · `< 40%` → vermelho · sem tentativa → vazio.

---

## 4. Espaçamento padrão

| Contexto | Valor |
|---|---|
| Gap entre cards no grid/lista | `12–16px` |
| Padding interno de card | `16–20px` |
| Gap entre botões de ação | `6–8px` |
| Margem inferior de breadcrumb | `18px` |
| Margem inferior de header de página | `20–24px` |
| Gap na linha de stats | `10–20px` |

---

## 5. Responsividade

**Breakpoints:**
- `≤ 600px` — banco de questões: cards empilham, ações em linha
- `≤ 700px` — turma/atividades: esconde tabela, mostra cards mobile (`.turma-mobile`)
- `≤ 520px` — ajustes gerais de padding e tamanho de fonte

**Área de toque mínima:** `44px` de altura para todos os botões de ação em mobile.

**Padrão para layout dual (tabela desktop / cards mobile):**
```html
<div class="turma-desktop"><!-- <table class="prof-tabela"> --></div>
<div class="turma-mobile"><!-- <div class="ativ-mcard"> por item --></div>
```
```css
.turma-mobile { display: none; }
@media (max-width: 700px) {
  .turma-desktop { display: none; }
  .turma-mobile  { display: block; }
}
```

---

## 6. Header de página padrão

```html
<div class="qb-header">
  <div>
    <h1 class="qb-titulo">Título da tela</h1>
    <p class="qb-subtitulo">Subtítulo ou contexto</p>
  </div>
  <a href="/..." class="btn-primary">+ Ação principal</a>
</div>
```

Para o dashboard (sem botão de ação no header):
```html
<div class="dash-page-header">
  <div>
    <h1 class="dash-page-title">Painel do Professor</h1>
    <p class="dash-page-sub">Bem-vindo de volta, {{ aluno_nome }}</p>
  </div>
</div>
```

---

## 7. Tom visual

- **Claro e profissional**: fundo `#f0f4ff`, branco nos cards, texto escuro.
- **Sem dark mode ativo**: o produto não tem tema escuro; não usar cores fixas como `#fff` em texto sem garantia de fundo escuro.
- **Mono para labels técnicos**: pesos de questão, IDs, badges de tipo — sempre `font-family: monospace`.
- **Sans para conteúdo**: enunciados, títulos, nomes de turma — `var(--sans)`.
- **Ações destrutivas sempre visuais**: Excluir nunca se parece com Editar. Use `.btn-danger`, nunca `.btn-ghost` ou `.prof-link`.
- **Confirmação antes de destruir**: sempre modal (não `confirm()`), com foco automático no botão "Cancelar".
