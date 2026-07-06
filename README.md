# LeDuk

Plataforma de atividades educacionais interativas self-hosted, construída sobre PocketBase + Flask + HTMX. Desenvolvida para o CETEP/LNAB (Alagoinhas, BA) com turmas EMI e PROEJA do curso Técnico em Análises Clínicas.

---

## Estrutura do repositório

```
leduk/
├── app.py                  ← aplicação Flask (factory create_app)
├── questao.py              ← lógica de validação e cálculo de score/nota
├── boletim.py              ← cálculo de boletim por unidade/disciplina + recuperação
├── utils/email.py          ← envio transacional via Resend (boas-vindas, reset de senha)
├── pb.py                   ← cliente HTTP para o PocketBase
├── gunicorn.conf.py        ← bind, workers, wsgi_app = "app:create_app()"
├── deploy.sh               ← pull → pip install → restart → health check
├── requirements.txt        ← dependências de produção
├── requirements-dev.txt    ← pytest, pytest-flask, responses
├── pytest.ini
├── IDENTIDADE-VISUAL.md    ← design system: paleta, componentes, responsividade
│
├── scripts/                      ← migrações idempotentes (criam collection ou verificam antes de alterar)
│   ├── migrate_boletim.py                 ← cria collections boletins/unidades/recuperacao_final
│   ├── migrate_tokens_senha.py            ← cria collection tokens_senha (reset de senha)
│   ├── migrate_matriculas.py              ← cria collection matriculas (aluno ↔ turma)
│   ├── migrate_formulario_cadastro.py     ← cria formularios_cadastro + campo matricula em users
│   ├── migrate_materiais.py               ← cria collection turma_materiais (pivô) + campo assunto + backfill
│   ├── migrate_turmas_publicas.py         ← cria campos publica/descricao (turmas) + aluno_email/aluno_turma (tentativas) — modo público
│   ├── migrate_tentativas_questao_optional.py ← torna questao e aluno_id opcionais em tentativas (histórico + modo público)
│   ├── verificar_modo_publico.py          ← diagnóstico + correção (--fix) do modo público: campos, regras e teste real de POST anônimo
│   └── migrate_provas.py                  ← cria collections templates_prova e provas (gerador de provas impressas)
│
│   (scripts de correção pontual já aplicados em produção foram removidos do
│   repositório — ver "Migrações históricas" na seção Collections PocketBase)
│
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── components/
│   │   ├── _questao_mc.html
│   │   ├── _questao_vf.html
│   │   ├── _questao_assoc.html
│   │   ├── _questao_aberta.html
│   │   ├── _feedback.html
│   │   ├── _placar.html
│   │   ├── _toggle_ativa.html
│   │   └── _drawer_professor.html  ← menu hambúrguer do professor (turmas + banco)
│   ├── quiz/
│   │   └── shell.html
│   ├── aluno/
│   │   ├── historico.html
│   │   ├── revisao.html
│   │   └── boletim.html          ← boletim do aluno (só se liberado)
│   ├── cadastro/
│   │   ├── redefinir_senha.html  ← formulário público de nova senha (via token)
│   │   ├── formulario.html       ← auto-cadastro público via link de convite
│   │   └── inativo.html          ← link de cadastro desativado / não encontrado
│   ├── publica/                  ← modo público (turmas sem matrícula, sem login)
│   │   ├── atividade.html        ← página pública da atividade (materiais + botão responder)
│   │   ├── identificar.html      ← nome/email/turma + confirmação de re-tentativa
│   │   ├── limite.html           ← limite de tentativas atingido / atividade não encontrada
│   │   └── resultado.html        ← placar do respondente público
│   ├── turma/
│   │   └── portal.html
│   ├── professor/
│   │   ├── dashboard.html
│   │   ├── turma.html              ← lista com excluir/clonar/copiar link
│   │   ├── atividade_form.html
│   │   ├── questoes.html           ← questões de uma atividade
│   │   ├── questao_form.html       ← criar/editar questão (todos os tipos + imagem)
│   │   ├── banco_questoes.html     ← banco reutilizável da disciplina (filtros + uso)
│   │   ├── banco_geral.html        ← banco geral (todas disciplinas) + seleção multidisciplinar
│   │   ├── atividade_multidisciplinar.html ← montar atividade com questões de várias disciplinas
│   │   ├── importar_questoes.html  ← importação JSON (colar/arquivo) com pré-visualização
│   │   ├── selecionar_questoes.html ← seletor do banco para adicionar à atividade
│   │   ├── turmas.html / turma_form.html         ← CRUD de turmas
│   │   ├── disciplinas.html / disciplina_form.html ← CRUD de disciplinas
│   │   ├── turma_disciplinas.html  ← vínculo turma ↔ disciplina (pivô)
│   │   ├── banco_materiais.html    ← banco de materiais da disciplina
│   │   ├── material_form.html      ← criar/editar material (vídeo/pdf/link/arquivo)
│   │   ├── selecionar_materiais.html ← seletor do banco para adicionar à turma
│   │   ├── turma_materiais.html    ← materiais vinculados a uma turma
│   │   ├── alunos.html / aluno_form.html ← gestão de alunos da turma (cadastro manual)
│   │   ├── formulario_relatorio.html ← cadastros via link público (+ exportar CSV)
│   │   ├── publico/                ← gestão de turmas/atividades públicas (modo público)
│   │   │   ├── index.html          ← lista turmas públicas + form de criação
│   │   │   ├── turma.html          ← atividades por disciplina + link público + contagem de respostas
│   │   │   ├── respostas.html      ← tabela de respondentes + exportar CSV + relatórios
│   │   │   ├── relatorio_geral.html      ← página HTML com todos os respondentes (imprimir/salvar PDF pelo navegador)
│   │   │   └── relatorio_individual.html ← comprovante individual com detalhamento por questão (imprimir/salvar PDF pelo navegador)
│   │   ├── provas/                 ← gerador de provas impressas com gabarito
│   │   │   ├── lista.html          ← lista de provas (editar/preview/imprimir/excluir)
│   │   │   ├── form.html           ← criação/edição — cabeçalho, instruções, seletor HTMX de questões
│   │   │   ├── seletor_questoes.html    ← fragmento HTMX: banco filtrado por disciplina/tipo/assunto
│   │   │   ├── _questoes_selecionadas.html ← fragmento HTMX: questões na prova (reordenar/remover)
│   │   │   ├── imprimir.html       ← layout de impressão (2 colunas, gabarito com quebra de página)
│   │   │   └── templates/form.html ← editor de templates de cabeçalho reutilizáveis
│   │   ├── boletim/                ← configurar/unidades/notas/relatorio do boletim
│   │   ├── components/
│   │   │   ├── _seletor_questoes.html ← cards com checkbox (reuso de questões)
│   │   │   ├── _aluno_acoes.html   ← botões HTMX (reenviar dados / redefinir senha)
│   │   │   ├── _formulario_box.html ← caixa do link público (criar/copiar/toggle)
│   │   │   └── _matricula_cell.html ← matrícula editável inline (HTMX)
│   │   ├── notas.html
│   │   └── notas_abertas.html
│   └── relatorio/
│       ├── turma.html
│       └── aluno.html
│
├── static/css/base.css     ← identidade visual + temas por disciplina
├── static/exemplos/questoes_exemplo.json ← exemplo de importação (todos os tipos)
│
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── questao_mc4.json
    │   ├── questao_vf.json
    │   └── questao_associativa.json
    ├── unit/
    │   ├── test_questao.py
    │   ├── test_score.py
    │   ├── test_peso.py
    │   ├── test_boletim.py       ← cálculo do boletim + bordas de recuperação
    │   └── test_email.py         ← envio via Resend (mock, payload, sem-chave)
    └── integration/
        ├── test_auth.py
        ├── test_rotas_atividade.py
        ├── test_rotas_htmx.py
        ├── test_portal_turma.py
        ├── test_tentativas.py
        ├── test_melhorias_ux.py
        ├── test_relatorios.py
        ├── test_professor.py
        ├── test_ciclo_atividade.py
        ├── test_gestao_atividade.py  ← smoke tests: excluir/clonar/CRUD questões
        ├── test_banco_questoes.py    ← banco reutilizável: filtros, clonar, reuso, uso
        ├── test_navegacao_professor.py ← drawer do professor + atalhos ao banco
        ├── test_gestao_escola.py     ← turmas/disciplinas/vínculos + banco de materiais
        ├── test_banco_geral.py       ← banco geral + atividade multidisciplinar
        ├── test_importar_questoes.py ← importação JSON (colar/arquivo, imagens)
        ├── test_questao_form.py      ← seções condicionais do form + navegação banco
        ├── test_boletim_rotas.py     ← rotas do boletim (config, toggles, notas, acesso)
        ├── test_senha_alunos.py      ← reset de senha (público/professor) + cadastro manual
        ├── test_cadastro_publico.py  ← auto-cadastro via link + gestão do formulário
        ├── test_materiais.py         ← upload multipart vs JSON, url_arquivo_material()
        ├── test_modo_publico.py      ← turmas públicas: identificação, limite de tentativas, comprovante
        └── test_provas.py            ← gerador de provas: CRUD, HTMX, tipos mistos, impressão, templates
```

---

## Stack técnico

| Componente | Tecnologia |
|---|---|
| API + banco + auth | PocketBase 0.22.20 (SQLite embutido) |
| Backend | Flask 3.x + Gunicorn (2 workers) |
| Frontend | HTMX 1.9.12 (fragmentos HTML, sem SPA) |
| Relatórios/PDF | HTML + `@media print` — impressão/"Salvar como PDF" pelo navegador (sem lib nativa) |
| Proxy reverso | Nginx + Let's Encrypt |
| Linguagem | Python 3.11 |

---

## Desenvolvimento local

### Pré-requisitos

- Python 3.11+
- PocketBase rodando em `http://127.0.0.1:8090` (ou ajustar `PB_URL`)

### Setup

```bash
git clone <repo>
cd leduk
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Rodar a aplicação

```bash
PB_URL=http://127.0.0.1:8090 python app.py
```

A aplicação sobe em `http://127.0.0.1:8091`.

### Rodar os testes

```bash
pytest
```

Os testes não dependem de PocketBase real — as chamadas HTTP são mockadas via `responses`.

```
tests/unit/        → lógica pura (sem rede, sem Flask)
tests/integration/ → rotas Flask com PocketBase mockado
```

**Resultado esperado:** 309 testes, todos passando.

---

## Rotas Flask

### Autenticação

| Método | Rota | Descrição |
|---|---|---|
| GET/POST | `/login` | Formulário de login via PocketBase JWT |
| GET | `/logout` | Limpa sessão e redireciona |
| GET/POST | `/redefinir-senha/<token>` | Definir nova senha via token (público; 410 se inválido/expirado/usado) |
| GET/POST | `/cadastro/<token>` | Auto-cadastro público via link de convite (404 se token inválido; login automático + boas-vindas) |

### Aluno

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/` | Home com atividades agrupadas por turma |
| GET | `/turma/<id>` | Portal da turma (disciplinas, atividades, materiais) |
| GET | `/turma/<id>/multidisciplinar` | Aba dedicada com atividades multidisciplinares da turma |
| GET | `/atividade/<id>` | Shell da atividade (inicia fila de questões) |
| GET | `/htmx/questao/<id>` | Fragmento HTML da questão |
| POST | `/htmx/responder` | Valida resposta e retorna feedback |
| GET | `/htmx/proxima/<ativ_id>` | Fragmento da próxima questão |
| GET | `/htmx/resultado/<ativ_id>` | Placar final |
| GET | `/aluno/historico` | Histórico — uma linha por atividade concluída, com data/hora da última tentativa |
| GET | `/aluno/atividade/<id>/revisao/<tent_id>` | Revisão detalhada com gabarito |

### Professor (requer role `professor` ou `admin`)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/professor/dashboard` | Dashboard com mapa de calor por turma |
| GET | `/professor/turma/<id>` | Gestão de atividades: editar, excluir, clonar, copiar link |
| GET/POST | `/professor/atividade/nova` | Criar nova atividade |
| GET/POST | `/professor/atividade/<id>/editar` | Editar atividade existente |
| POST | `/professor/atividade/<id>/excluir` | Excluir atividade (com confirmação) |
| POST | `/professor/atividade/<id>/clonar` | Clonar atividade (cópia inativa) |
| POST | `/professor/atividade/<id>/toggle-ativa` | Ativar/desativar (HTMX) |
| GET | `/professor/atividade/<id>/questoes` | Questões da atividade |
| GET/POST | `/professor/atividade/<id>/questoes/nova` | Criar questão (todos os tipos + imagem) |
| GET | `/professor/atividade/<id>/selecionar-questoes` | Selecionar questões do banco para adicionar |
| POST | `/professor/atividade/<id>/adicionar-questoes` | Adicionar questões selecionadas (sem duplicar) |
| GET/POST | `/professor/questao/<id>/editar` | Editar enunciado/peso/assunto/imagem de questão |
| POST | `/professor/questao/<id>/clonar` | Clonar questão (registro independente) |
| POST | `/professor/questao/<id>/reclassificar` | Mover questão para outra disciplina/assunto |
| POST | `/professor/questao/<id>/excluir` | Excluir questão (e remover da atividade) |
| GET | `/professor/disciplina/<id>/banco-questoes` | Banco da disciplina — gerenciar questões (criar/editar/clonar/excluir) |
| GET/POST | `/professor/disciplina/<id>/questao/nova` | Criar questão direto no banco da disciplina |
| GET/POST | `/professor/disciplina/<id>/importar-questoes` | Importar questões via JSON (dedup, rollback, imagens link/base64) |
| POST | `/professor/disciplina/<id>/questoes/excluir-em-massa` | Excluir várias questões selecionadas (cascade) |
| GET | `/professor/banco-questoes` | Seletor multidisciplinar — selecionar questões de qualquer disciplina (filtros) |
| GET/POST | `/professor/atividade/multidisciplinar` | Montar atividade com questões de várias disciplinas |
| GET | `/professor/atividade/<id>/notas` | Notas dos alunos com liberação em lote |
| POST | `/professor/atividade/<id>/liberar-notas` | Liberar notas selecionadas |
| GET | `/professor/atividade/<id>/notas-abertas` | Corrigir questões abertas |
| POST | `/professor/questao-aberta/<tent_id>/avaliar` | Gravar nota de questão aberta |
| GET | `/professor/turmas` | Gerenciar turmas (CRUD) |
| GET/POST | `/professor/turma/nova` · `/professor/turma/<id>/editar` | Criar/editar turma |
| POST | `/professor/turma/<id>/excluir` | Excluir turma — se houver vínculos, pede confirmação explícita e então faz cascade (matrículas, disciplinas, formulário, materiais/boletim; tentativas e atividades são preservadas e desvinculadas) |
| GET | `/professor/disciplinas` | Gerenciar disciplinas (CRUD) |
| GET/POST | `/professor/disciplina/nova` · `/professor/disciplina/<id>/editar` | Criar/editar disciplina |
| POST | `/professor/disciplina/<id>/excluir` | Excluir disciplina (bloqueado se houver vínculos) |
| GET | `/professor/turma/<id>/disciplinas` | Vincular/desvincular disciplinas da turma (pivô) |
| POST | `/professor/turma/<id>/disciplinas/vincular` · `/desvincular/<vinc_id>` | Gerenciar vínculo |
| GET | `/professor/disciplina/<id>/banco-materiais` | Banco de materiais da disciplina (filtros + uso) |
| GET/POST | `/professor/material/novo` · `/professor/material/<id>/editar` | Criar/editar material |
| POST | `/professor/material/<id>/clonar` · `/reclassificar` · `/excluir` | Clonar/reclassificar/excluir (cascade) |
| GET | `/professor/turma/<id>/materiais` | Materiais vinculados à turma |
| GET | `/professor/turma/<id>/materiais/selecionar` | Selecionar materiais do banco |
| POST | `/professor/turma/<id>/materiais/adicionar` · `/remover/<vinc_id>` | Vincular/desvincular (sem duplicar) |
| GET/POST | `/professor/turma/<id>/boletim` | Configurar boletim (média de aprovação, ativo, liberado, ano) |
| POST | `/professor/turma/<id>/boletim/ativar` · `/liberar` | Toggles de ativo / liberado |
| GET | `/professor/turma/<id>/boletim/unidades` | Gerenciar unidades (atividades, recuperação) |
| POST | `/professor/turma/<id>/boletim/unidade/nova` · `/<uid>/editar` · `/<uid>/excluir` | CRUD de unidades |
| POST | `/professor/turma/<id>/boletim/rec-final` | Salvar recuperação final por disciplina |
| GET | `/professor/turma/<id>/boletim/notas` | Mapa de calor aluno × unidade × disciplina |
| GET | `/professor/turma/<id>/boletim/relatorio` | Relatório de médias finais e situação |
| GET | `/professor/aluno/<aluno_id>/boletim/<turma_id>` | Boletim individual (visão do professor) |
| GET | `/professor/turma/<id>/alunos` | Lista de alunos matriculados (ações por aluno) |
| GET/POST | `/professor/turma/<id>/alunos/novo` | Cadastro manual de aluno (cria user + matrícula) |
| POST | `/professor/aluno/<id>/redefinir-senha` | Gera token e envia link de redefinição (HTMX) |
| POST | `/professor/aluno/<id>/reenviar-boas-vindas` | Gera nova senha temporária e reenvia acesso (HTMX) |
| POST | `/professor/aluno/<id>/matricula` | Edita a matrícula do aluno inline (HTMX) |
| POST | `/professor/turma/<id>/formulario/criar` · `/toggle` | Cria / ativa-desativa o link público de cadastro |
| GET | `/professor/turma/<id>/formulario/relatorio` · `.csv` | Cadastros via formulário (tela + exportação CSV) |

### Aluno — boletim

| Método | Rota | Descrição |
|---|---|---|
| GET | `/aluno/boletim/<turma_id>` | Boletim do aluno logado (403 se não liberado) |

### Modo público (turmas sem matrícula)

Rotas públicas, sem login — qualquer pessoa acessa via link direto:

| Método | Rota | Descrição |
|---|---|---|
| GET | `/publica/<ativ_id>` | Página da atividade (materiais + botão "Responder"); 404 se a turma não for pública |
| GET/POST | `/publica/<ativ_id>/identificar` | Nome/email/turma; confirma re-tentativa se o email já respondeu; bloqueia no limite de `max_tentativas` |
| GET | `/publica/<ativ_id>/resultado` | Placar do respondente público |

O fluxo de questões (`/atividade/<id>`, `/htmx/questao`, `/htmx/responder`, `/htmx/proxima`) é o
mesmo do aluno logado — o decorator `requer_login_ou_publico` aceita sessão autenticada **ou**
sessão pública (`session["pub_modo"]`), e as tentativas são gravadas com `aluno_id=""` +
`aluno_email`/`aluno_turma` para identificar o respondente sem conta.

Gestão do professor (requer role `professor`/`admin`):

| Método | Rota | Descrição |
|---|---|---|
| GET | `/professor/publico` | Lista turmas públicas + formulário de criação |
| POST | `/professor/publico/turma/nova` | Cria turma com `publica=true`, `ativa=true` |
| GET | `/professor/publico/turma/<id>` | Atividades por disciplina, link público e contagem de respondentes |
| GET | `/professor/atividade/<id>/respostas-publicas` | Tabela de respondentes (nome, email, turma, nota, data) |
| GET | `/professor/atividade/<id>/respostas-publicas.csv` | Exportação CSV |
| GET | `/professor/atividade/<id>/relatorio-publico` | Página HTML com todos os respondentes — botão "Imprimir / Salvar PDF" usa o navegador |
| GET | `/professor/atividade/<id>/relatorio-publico/<email>` | Comprovante individual (devolutiva), com detalhamento por questão — enunciado, alternativas/afirmações/pares marcados vs. gabarito, feedback; mesmo botão de impressão |

Ambos os relatórios são páginas HTML normais (não geram PDF no servidor): o botão
"🖨️ Imprimir / Salvar PDF" chama `window.print()` e o navegador do professor faz a
conversão via "Salvar como PDF" no diálogo de impressão. A versão anterior gerava o PDF
no servidor com WeasyPrint — removido porque o suporte a flexbox da lib é limitado e
falhava silenciosamente em produção, cortando conteúdo do detalhamento sem erro visível.
Impressão pelo navegador é mais confiável e elimina uma dependência nativa pesada.

Turmas públicas exibem um badge `🌐 Pública` (`.badge-publica` em `base.css`) em todas as telas
que listam turmas no painel do professor.

### Provas impressas (gerador com gabarito)

Monta provas em papel a partir do mesmo banco de questões usado pelas atividades digitais
(mc4/mc5/vf/associativa/aberta), com cabeçalho reutilizável entre provas e gabarito gerado
automaticamente.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/professor/provas` | Lista provas salvas |
| GET/POST | `/professor/provas/nova` | Formulário / criação — título, cabeçalho, instruções (pré-preenchidas) |
| GET/POST | `/professor/provas/<id>/editar` | Editar dados básicos da prova |
| POST | `/professor/provas/<id>/excluir` | Excluir prova |
| GET | `/professor/provas/<id>/preview` · `/imprimir` | Página HTML pronta para impressão — botão "Imprimir / Salvar PDF" via `window.print()` |
| GET | `/professor/provas/templates` | Lista + formulário de templates de cabeçalho reutilizáveis |
| POST | `/professor/provas/templates/novo` · `/<id>/editar` · `/<id>/excluir` | CRUD de templates |
| GET | `/htmx/provas/questoes?prova_id=&disciplina=&tipo=&assunto=` | Fragmento HTMX: banco filtrado, exclui questões já adicionadas |
| POST | `/htmx/provas/<id>/adicionar-questao/<qid>` · `/remover-questao/<qid>` | Adiciona/remove questão do array `questoes[]` (persiste na hora) e retorna o fragmento atualizado |
| POST | `/htmx/provas/<id>/reordenar` | Troca a posição de uma questão com a vizinha (`questao_id` + `direcao=cima/baixo`) e retorna o fragmento atualizado |

**Fluxo em duas etapas:** criar a prova (título/cabeçalho/instruções) primeiro; o seletor de
questões via HTMX só aparece depois de existir um `prova_id` para anexar. Cada clique em
"+ Adicionar", "✕" ou "↑"/"↓" já persiste no PocketBase e devolve o fragmento
`_questoes_selecionadas.html` atualizado — não há um botão "salvar questões" separado.

**Impressão (`imprimir.html`):** página HTML autocontida (sem geração de PDF no servidor —
mesma decisão do modo público, ver acima). Questões em grade CSS de 2 colunas
(`columns: 2`); mc4/mc5 e vf usam um bloco inicial (`questao-bloco-inicial`, enunciado +
2 primeiros itens, `break-inside: avoid`) seguido dos itens restantes soltos
(`.alternativa`/`.vf-item`, cada um com `break-inside: avoid` individual) — assim a questão
"antecipa" na coluna atual em vez de saltar inteira para a próxima quando é longa. Marcação
de resposta nunca usa bolinha/checkbox de UI de tela: mc4/mc5 começa direto pela letra
(`A) texto`), V/F já usa `( V ) ( F )`, e só a coluna A da associativa usa parênteses em
branco (`(      )`) para o estudante escrever a letra correspondente à mão. Questão
associativa ocupa uma única coluna (`column-span: none`), com coluna A e B empilhadas. O
peso de cada questão não aparece na folha impressa (só é usado internamente para o
cálculo da nota). Após a última questão, uma linha "Sucesso!" em itálico alinhado à
direita. Gabarito numa página separada (`page-break-before: always`) com grade compacta
mostrando só a letra correta (mc4/mc5), V/F por afirmação (vf), ou apenas `Assoc.`/`Aberta`
para os tipos que exigem correção manual do professor.

**Embaralhamento:** a flag `embaralhar` da prova sorteia a ORDEM das questões na página,
com seed determinístico pelo `id` da prova — reimprimir a mesma prova sempre gera a mesma
sequência (gabarito nunca dessincroniza da folha impressa). Já a coluna B de questões
associativas é **sempre** embaralhada (independente dessa flag, seed por `prova_id +
questao_id`) — sem isso, o item certo cairia sempre na mesma linha do item da coluna A,
entregando a resposta de graça.

### Relatórios

| Método | Rota | Descrição |
|---|---|---|
| GET | `/relatorio/turma/<id>` | Relatório agregado por turma |
| GET | `/relatorio/aluno/<id>` | Histórico individual |

### Fluxo HTMX

```
GET /atividade/<id>          ← carrega shell + primeira questão via hx-trigger
        ↓
GET /htmx/questao/<id>       ← renderiza fragmento mc / vf / associativa / aberta
        ↓
POST /htmx/responder         ← valida resposta, grava tentativa no PocketBase
        ↓
_feedback.html               ← exibe correto/incorreto + feedback
        ↓
GET /htmx/proxima/<ativ_id>  ← próxima questão (repete até o fim)
        ↓
_placar.html                 ← placar final injetado em #questao-area
```

---

## Lógica de questões (`questao.py`)

Funções puras, sem dependência de Flask ou rede — testáveis isoladamente.

| Função | Entrada | Saída |
|---|---|---|
| `validar_mc(questao, resposta)` | letra selecionada (`"A"`) | `{correta, score_raw, score_max, feedback, resposta_correta}` |
| `validar_vf(questao, respostas)` | `{str(ordem): bool}` | `{correta, score_raw, score_max, feedback}` |
| `validar_associativa(questao, respostas)` | `{str(ordem): valor_b}` | `{correta, score_raw, score_max, feedback}` |
| `calcular_score(tipo, questao, resposta)` | qualquer tipo | `(score_raw, score_max)` |
| `calcular_valor_ponto(atividade, pesos)` | atividade + lista de pesos | valor em pontos por unidade de peso |
| `calcular_nota_final(respostas, atividade)` | respostas da sessão + atividade | nota em pontos (1 casa decimal) ou `None` |

### Pontuação por peso

Quando a atividade tem `valor_total > 0`, a nota é calculada proporcionalmente ao peso de cada questão:

```
valor_ponto = valor_total / soma_de_todos_os_pesos
contribuição_q = (score_raw / score_max) * peso_q * valor_ponto
nota_final = soma das contribuições
```

Questões abertas sem correção contribuem 0 até o professor avaliar.

---

## Collections PocketBase

### IDs fixos

| Collection | ID | Descrição |
|---|---|---|
| users | `_pb_users_auth_` | Alunos e professores |
| turmas | `0xiasmpkvxqig9c` | Turmas (EMI / PROEJA / FIC / EJA) + `publica` (bool) e `descricao` (text) para o modo público |
| disciplinas | `m7urzbvhokcqdz0` | Disciplinas com cor e ícone por tema |
| turma_disciplina | `503sn0usao2qvp9` | Pivô N:N turma ↔ disciplina |
| questoes | `sdtq4w1im9dunfw` | Banco central de questões + imagem + `assunto` |
| alternativas | `jf69g6b4qr80hq3` | Opções mc4/mc5 com feedback e imagem |
| itens_vf | `dkc5b8csbsus7es` | Afirmações V/F ordenadas |
| pares_associativos | `8okcm31re6gxm4p` | Coluna A : Coluna B com imagens |
| tentativas | `2cgvat5j77ne31y` | Log de respostas + registro-pai da tentativa (campos: `atividade`, `aluno_id` opcional, `aluno_email`/`aluno_turma` para respondente público, `numero_tentativa`, `questoes_respondidas`, `nota_final`) |
| atividades | `44qehlo0jku49lq` | Agrupa `questoes[]` por turma/disciplina (`multidisciplinar`, `max_tentativas`, `tempo_limite`, `valor_total`, `disponivel_de/ate`, `nota_automatica`, `exibir_feedback_pos`, `embaralhar`, `modo_prova`, `ativa`) |
| materiais | `izszkyi16wtznur` | Vídeos/PDFs/links/arquivos do banco da disciplina (+ `assunto` + `arquivo`); campo legado `turma` (direto, required) coexiste com o pivô `turma_materiais` |
| turma_materiais | — | Pivô N:N turma ↔ material — criada por `scripts/migrate_materiais.py` |

> `turma_materiais` não tem ID fixo seedado aqui: é criada dinamicamente pela
> migração (resolve os IDs em runtime). O ID de `materiais` (`izszkyi16wtznur`)
> é usado por `pb.url_arquivo_material()` para montar a URL pública dos arquivos.

Collections criadas por migração posterior (sem ID fixo seedado): `boletins`,
`unidades`, `recuperacao_final` (boletim); `tokens_senha` (reset de senha);
`matriculas` (aluno ↔ turma, com `origem` = `manual`/`formulario`) e
`formularios_cadastro` (link público por turma). A collection `users` também
ganhou o campo `matricula` (text, opcional).

`templates_prova` (`nome`, `cabecalho_html`, `instrucoes`, `professor`) e `provas`
(`titulo`, `template` → templates_prova, `cabecalho_html`, `instrucoes`, `questoes[]` →
questoes — ordem do array = ordem de impressão —, `professor`, `embaralhar`) dão suporte
ao gerador de provas impressas (`scripts/migrate_provas.py`).

### Migrações históricas (já aplicadas, removidas do repositório)

Os scripts abaixo corrigiam campos/regras em collections que já existiam
antes deste código (seedadas fora dos scripts deste repo — ver nota acima).
Cada um já foi executado com sucesso na produção atual; como o único
propósito era sincronizar o schema existente com o que o código passou a
exigir, foram removidos do repositório após a confirmação. O código-fonte
de cada um continua disponível no histórico do git (`git log --all --oneline
-- scripts/<nome>`), caso uma instalação futura precise reaplicá-los.

| Script removido | O que fazia |
|---|---|
| `migrate_tentativas.py` | Adicionou o campo `atividade` (relation) em `tentativas` e migrou registros legados que usavam o campo `disciplina` |
| `add_assunto_questoes.py` | Adicionou o campo `assunto` em `questoes` |
| `add_multidisciplinar_atividades.py` | Adicionou o campo bool `multidisciplinar` em `atividades` |
| `migrate_atividades_campos.py` | Adicionou os campos de configuração faltantes em `atividades` (`max_tentativas`, `tempo_limite`, `valor_total`, `disponivel_de/ate`, `nota_automatica`, `exibir_feedback_pos`, `embaralhar`, `modo_prova`, `ativa`) |
| `migrate_tentativas_progresso.py` | Adicionou `questoes_respondidas`, `numero_tentativa` e `nota_final` em `tentativas` |
| `migrate_materiais_rules.py` | Corrigiu `createRule`/`updateRule` de `materiais` para permitir upload multipart |
| `migrate_users_viewrule.py` | Corrigiu `viewRule` de `users` para professores/admins verem nome e email do aluno via `expand` |
| `cleanup_questoes_duplicadas.py` | Ferramenta de limpeza pontual para questões duplicadas/órfãs de um bug histórico já corrigido no código (ver `LESSONS-LEARNED.md` §5 e §7) |

### Tipos de questão

| Tipo | Descrição | Suporte a imagem |
|---|---|---|
| `mc4` | Múltipla escolha — 4 alternativas | questão + cada alternativa |
| `mc5` | Múltipla escolha — 5 alternativas | questão + cada alternativa |
| `vf` | Lista de afirmações V/F ordenadas | por afirmação |
| `aberta` | Resposta dissertativa (corrigida pelo professor) | questão |
| `associativa` | Pares coluna A : coluna B | imagem por par |

### Campo `atividade` na collection `tentativas`

A collection `tentativas` armazena dois tipos de registro:

- **Registro-pai da tentativa** — criado em `/atividade/<id>` com `atividade`, `aluno_id`, `aluno_nome`, `numero_tentativa`, `concluida`, `nota_liberada`, `questoes_respondidas`
- **Registro de resposta** — criado em `/htmx/responder` com `atividade`, `questao`, `tipo_questao`, `resposta_dada`, `correta`, `score_raw`, `score_max`, `tentativa_id`

O campo `atividade` (relation → `atividades`) é obrigatório em ambos; registros legados que
usavam o campo `disciplina` já foram migrados em produção (ver "Migrações históricas" acima).

Os campos `questao` (registro de resposta) e `aluno_id` (ambos os tipos) são **opcionais**:
`questao` é anulado quando a questão referenciada é excluída (preserva o histórico do aluno);
`aluno_id=""` identifica um respondente do modo público, sem conta — ver "Modo público" abaixo.

### Banco de questões reutilizável (campo `assunto`)

Questões pertencem ao **banco da disciplina** (`questoes.disciplina`), não a uma
atividade específica. Uma atividade apenas referencia IDs em `atividades.questoes[]`,
então a mesma questão pode ser reusada em várias atividades sem duplicar o registro.

O campo livre `assunto` (text, opcional) organiza e filtra as questões dentro da
disciplina (ex: "Fases do LIS", "Imunoglobulinas").

Operações sobre o banco (em `pb.py`): `listar_questoes_disciplina` (filtros por
tipo/assunto/dificuldade), `clonar_questao` (duplica questão + subitens como
registro independente), `reclassificar_questao` (move disciplina/assunto sem
quebrar vínculos), `contar_uso_questao` (em quantas atividades a questão aparece),
`remover_questao_de_todas_atividades` (cascade manual ao excluir).

Ao excluir uma questão, o sistema faz **cascade manual**: remove o ID de
`atividades.questoes[]` de todas as atividades que a referenciam antes de apagar
o registro — assim nenhuma atividade fica com vínculo órfão. Na tela do banco, se
a questão está em uso, a confirmação avisa explicitamente em quantas atividades.

### Banco de materiais reutilizável (campo `assunto` + `turma_materiais` + upload de arquivo)

Materiais seguem o mesmo modelo das questões: pertencem ao **banco da disciplina**
(ganharam o campo `assunto`) e a turma os "usa" através da collection pivô
`turma_materiais` (`turma`, `material`, `ordem`, `ativo`). Um mesmo material pode
aparecer em várias turmas sem duplicar o registro.

Migração (idempotente — adiciona `assunto`, cria `turma_materiais`, faz backfill
dos materiais legados que tinham `turma` preenchido):

```bash
PB_URL=https://pb.repoept.duckdns.org \
PB_ADMIN_EMAIL=admin@exemplo.com \
PB_ADMIN_PASSWORD=senha \
  python scripts/migrate_materiais.py
```

**Leitura retrocompatível:** `pb.listar_materiais` lê via `turma_materiais`
(expand `material`, filtrando pela disciplina). Se a collection pivô ainda não
existir (pré-migração) ou a consulta falhar, cai no filtro legado
`materiais.turma` — o portal do aluno nunca quebra. Uma vez migrada, a leitura
confia no pivô (mesmo vazio) para não exibir dados legados defasados.

Exclusão de material faz **cascade manual** em `turma_materiais` antes de apagar
o registro. Exclusão de **disciplina** continua **bloqueada** quando há vínculos
(turma_disciplina, questões, materiais), com aviso explícito na tela. Exclusão de
**turma** funciona diferente: com vínculos, pede confirmação explícita e então faz
o cascade completo — remove matrículas, `turma_disciplina`, formulário de cadastro,
`turma_materiais` e materiais legados; anula (não deleta) a referência em tentativas
e atividades, preservando o histórico.

**Upload de arquivo (campo `arquivo`, tipo `file`):** materiais dos tipos `pdf` e
`arquivo` aceitam upload direto. O formulário usa `XMLHttpRequest` com evento
`progress` para exibir barra de progresso durante o envio (até 50 MB). O template
ainda aceita URL externa como alternativa ao upload.

`pb.url_arquivo_material(material)` resolve a URL pública do arquivo:
- se `material["arquivo"]` estiver preenchido → `{PB_PUBLIC_URL}/api/files/izszkyi16wtznur/{id}/{arquivo}`
- senão → `material["url"]`

`PB_PUBLIC_URL` deve ser definido no serviço (`/etc/systemd/system/leduk.service`); sem
ela, o método usa `base_url` (interno `127.0.0.1:8090`, não acessível pelo aluno).

A collection `materiais` precisa de `createRule`/`updateRule` = `@request.auth.id != ""`
para permitir o upload multipart (já corrigido em produção — ver "Migrações históricas").
Se um ambiente novo apresentar 403 no upload, confirme essas regras em `/_/` → Collections →
materiais → API Rules.

### Embaralhamento de alternativas

Para mc4/mc5, as alternativas são embaralhadas por aluno usando `random.Random(tentativa_id + questao_id)` — seed estável, determinístico por tentativa. Os **badges exibidos** (A, B, C, D) sempre seguem a posição sequential na tela; o `value` do radio mantém a letra original para que a validação da resposta funcione corretamente.

Para questões `associativa`, dois RNGs independentes embaralham: as **linhas** (coluna A) e as **opções do dropdown** (coluna B) com seeds `seed` e `seed + "_opcoes"` respectivamente — garantindo ordens distintas entre si.

### Modo prova (`campo modo_prova` em atividades)

Quando `modo_prova = true`, a atividade funciona como uma prova controlada:

- **Durante**: o feedback pós-resposta é suprimido — o fragmento `_feedback.html` emite apenas um `<div hx-trigger="load">` que avança automaticamente para a próxima questão, sem mostrar "Resposta correta/incorreta".
- **Após**: o placar exibe apenas nota final, percentual de aproveitamento e barra de progresso. São ocultados: detalhamento por questão (Q1 ✓/✗ pts), contagem de corretas, badge "Aguardando correção" e link "Ver gabarito".

O campo `modo_prova` é configurável no formulário de atividade (checkbox "🔒 Modo prova"). É gravado como `bool` via `_form_to_atividade()` e persistido na sessão Flask em `session["modo_prova"]` ao iniciar a atividade.

### Importação de questões via JSON

`/professor/disciplina/<id>/importar-questoes` aceita uma lista de questões (ou
`{"questoes": [...]}`) colada num textarea ou enviada como arquivo `.json`. As
questões entram no banco da disciplina. Exemplo completo cobrindo todos os tipos
em [`static/exemplos/questoes_exemplo.json`](static/exemplos/questoes_exemplo.json).

Campos por questão: `tipo` (mc4/mc5/vf/aberta/associativa), `enunciado`, `peso`,
`dificuldade`, `assunto`, `feedback_geral`, `imagem`; e por tipo:
`alternativas[]` (mc4/mc5), `itens_vf[]` (vf), `pares[]` (associativa).

**Normalização de campos (JSON gerado por ferramentas externas, ex: NotebookLM):**
`letra` em cada alternativa é opcional — se ausente, é gerada automaticamente
pela posição (A, B, C, D, E), sem nunca sobrescrever uma letra já informada.
Em `itens_vf`, `texto` é aceito como alias de `afirmacao`, `gabarito` como
alias de `correta` (sempre normalizado *para* `correta` — nunca o inverso,
já que `correta` é o nome real do campo no PocketBase), e `ordem` é gerada
pela posição quando ausente. Essa normalização roda tanto na pré-visualização
quanto na importação real, para manter os dois passos consistentes.

O campo `imagem` (na questão e em cada alternativa) aceita **URL** `https://...`
ou **data URI base64** `data:image/png;base64,...` — em ambos os casos o conteúdo
é baixado/decodificado e enviado como arquivo ao PocketBase (multipart). A
importação é *best-effort*: questões válidas são criadas e as inválidas são
reportadas individualmente (tipo desconhecido, enunciado vazio, MC sem gabarito).

O fluxo é em dois passos: **Pré-visualizar** (dry-run, sem gravar nada) mostra um
resumo — quantas serão criadas, contagem por tipo e o status de cada questão
(válida ou o motivo do problema) — e só então **Confirmar importação** grava de
fato. Dá para ajustar o JSON e pré-visualizar de novo antes de confirmar.

**Deduplicação:** antes de criar cada questão, o import compara `(tipo,
enunciado normalizado)` contra o banco existente **e** contra o que já foi
processado no mesmo lote — questões idênticas são puladas (não recriadas) e
reportadas separadamente dos erros de validação, tanto na pré-visualização
quanto no resultado final.

**Atomicidade:** se a criação de um subitem (alternativa/item V-F/par) falhar
depois que a questão-pai já foi gravada, a questão-pai é removida (rollback
best-effort) em vez de ficar órfã no banco só com o enunciado, sem
alternativas — ver `LESSONS-LEARNED.md` § 5. Falhas de permissão (HTTP 403)
são reportadas de forma explícita ("permissão negada — verifique as regras de
acesso da collection") em vez de uma mensagem genérica.

Questões duplicadas/órfãs de importações anteriores a essa correção já foram
limpas em produção com `scripts/cleanup_questoes_duplicadas.py` (removido do
repositório — ver "Migrações históricas"; disponível no histórico do git se
for necessário reaplicar).

**Seleção e exclusão em massa:** o banco por disciplina (`banco_questoes.html`)
tem checkbox por questão + "Selecionar todas" + "Excluir selecionadas", que
faz o mesmo cascade da exclusão individual, numa única confirmação: remove o
ID de `atividades.questoes[]` que referenciam a questão, **depois apaga os
subitens** (alternativas/itens_vf/pares_associativos) e só então a questão —
o PocketBase recusa (400) apagar um registro ainda referenciado por uma
relation obrigatória sem `cascadeDelete` habilitado nela (ver
`LESSONS-LEARNED.md` § 8). Se mesmo assim a exclusão falhar, a rota não
quebra (500): captura o erro, loga, e redireciona com um aviso legível em vez
de propagar a exceção.

### Boletim (collections `boletins`, `unidades`, `recuperacao_final`)

Cada turma tem **um** boletim (`media_aprovacao`, `ativo`, `liberado`, `ano`).
O boletim tem **N unidades por disciplina** (`numero`, `titulo`, `atividades[]`,
`rec_atividade`, `rec_nota_manual`) e **uma recuperação final por disciplina**.

Cálculo (módulo puro `boletim.py`, sem rede — totalmente testado em
`tests/unit/test_boletim.py`):

```
nota_unidade   = (Σ pontos do aluno / Σ valor_total) × 10   # melhor tentativa; não realizada = 0
rec (unidade)  = max(rec_atividade, rec_nota_manual)        # só substitui se for maior; vazia → mantém
media          = média simples das notas de unidade (após rec)
rec_final      = mesma lógica, por disciplina
media_final    = max(media, rec_final)
situação: aprovado (≥ média) · recuperação (< média e rec final pendente) · reprovado
```

Migração (idempotente, cria as 3 collections resolvendo IDs em runtime):

```bash
PB_URL=... PB_ADMIN_EMAIL=... PB_ADMIN_PASSWORD=... python scripts/migrate_boletim.py
```

O boletim do aluno só aparece quando `liberado=true` (senão a rota responde 403);
o card "📊 Ver meu boletim" só surge no portal quando `ativo=true`. A leitura no
portal é resiliente: se a collection `boletins` ainda não existir (pré-migração),
o portal funciona normalmente sem o card.

### Email transacional e redefinição de senha

`utils/email.py` envia via **Resend** (`RESEND_API_KEY` no ambiente — nunca
hardcodado). Sem a chave, o envio é um no-op que retorna `False`; todo envio é
**best-effort** — se o Resend falhar, o cadastro/ação já feito não é revertido.

Redefinição de senha (collection `tokens_senha`):
- token gerado com `secrets.token_urlsafe(32)` (não UUID)
- `expira_em` = agora + 24h, **verificado no servidor** ao abrir o link
- token de uso único: marcado `usado=true` imediatamente após redefinir
- link inválido/expirado/usado → página de erro (HTTP 410)

O professor dispara, por aluno (HTMX inline, na lista de alunos da turma):
**🔑 Redefinir senha** (gera token + envia link) e **📧 Reenviar dados de acesso**
(gera nova senha temporária de 8 caracteres, atualiza no PocketBase e reenvia).
Cadastro manual (`/professor/turma/<id>/alunos/novo`) cria o `user` (role=aluno)
+ `matricula` (origem=manual) e, opcionalmente, envia o email de boas-vindas.

### Auto-cadastro público (link de convite)

Cada turma pode ter um `formularios_cadastro` com um `token` e um flag `ativo`.
O professor cria/ativa/desativa o link na página de alunos (com copiar-link) e
acompanha os cadastros em um relatório com exportação CSV.

`/cadastro/<token>` (público, sem login):
- token inexistente → **404**; formulário inativo → página "não está mais disponível"
- valida nome/email/senha (mín. 8 caracteres, com confirmação); email duplicado → erro inline
- cria `user` (role=aluno) + `matricula` (origem=`formulario`), faz **login
  automático** (grava sessão) e redireciona ao portal; email de boas-vindas
  best-effort (não reverte o cadastro se falhar)

O campo `matricula` (em `users`) fica vazio no auto-cadastro e no cadastro manual;
o professor preenche depois — editável **inline via HTMX** na lista de alunos e
exibido no relatório do formulário.

### Diagrama de relacionamentos

```
turmas ──── turma_disciplina ──── disciplinas
   │                                   │
   │                          ┌────────┴────────┐
   │                       questoes          materiais
   │                  (mc4/mc5/vf/...)   (vídeo/pdf/link/arquivo)
   │                          │           + assunto (banco)
   │         ┌────────────────┼──────────┐
   │         │                │          │
   │   alternativas       itens_vf  pares_associativos
   │   (A/B/C/D/E)       (afirmações) (col_A : col_B)
   │                                       │
   └──── turma_materiais ──────────────────┘
        (pivô: turma usa material)

atividades  → agrupa questoes[] por turma + disciplina
tentativas  → log de respostas + registro-pai da tentativa
```

### Ordem de criação obrigatória

O PocketBase rejeita campos `relation` que apontam para collections inexistentes. Criar sempre nessa ordem:

```
1. turmas
2. disciplinas
3. turma_disciplina   (depende de turmas + disciplinas)
4. questoes           (depende de disciplinas)
5. alternativas       (depende de questoes)
6. itens_vf           (depende de questoes)
7. pares_associativos (depende de questoes)
8. materiais          (depende de disciplinas)
9. turma_materiais    (depende de turmas + materiais)
10. tentativas        (depende de turmas + disciplinas + questoes)
11. atividades        (depende de turmas + disciplinas + questoes)
```

### Campos `bool` nunca devem ser `required: true`

O PocketBase trata `false` como valor vazio em campos bool obrigatórios e rejeita a inserção com `validation_required`. Sempre usar `"required": false` em campos bool.

**Auditoria (2026-07):** todos os `scripts/migrate_*.py` e `pb.py` foram revisados —
nenhuma ocorrência de `bool` com `required: True`. Nenhum script cria/altera o
schema de `alternativas` ou `itens_vf` (pré-seedadas fora deste conjunto de
scripts); se algum script futuro precisar tocar essas collections, os campos
`correta`/`gabarito` devem seguir a mesma regra. Detalhes e mais lições em
[`LESSONS-LEARNED.md`](LESSONS-LEARNED.md).

### Regras de acesso (listRule / viewRule)

| Collection | listRule | viewRule | createRule | Observação |
|---|---|---|---|---|
| turmas | `""` | `""` | `@request.auth.id != ""` | leitura pública, escrita autenticada |
| disciplinas | `""` | `""` | `@request.auth.id != ""` | leitura pública, escrita autenticada |
| questoes | `""` | `""` | `@request.auth.id != ""` | leitura pública, escrita autenticada |
| alternativas | `""` | `""` | `""` | leitura + escrita pública (seed) |
| itens_vf | `""` | `""` | `@request.auth.id != ""` | leitura pública, escrita autenticada |
| pares_associativos | `""` | `""` | `@request.auth.id != ""` | leitura pública, escrita autenticada |
| atividades | `""` | `""` | `@request.auth.id != ""` | leitura pública, escrita autenticada |
| materiais | `""` | `""` | `@request.auth.id != ""` | obrigatório para upload multipart |
| users | admin-only | `@request.auth.id != ""` | — | `viewRule` aberta a qualquer usuário autenticado — necessária para o `expand=aluno` em `matriculas` mostrar nome/email em vez do ID bruto |
| tentativas | `""` | `""` | `""` | `listRule`/`createRule`/`updateRule` abertos — o modo público grava/lê tentativas sem login (`aluno_id=""`); ver `scripts/verificar_modo_publico.py` |

**Convenção das migrações:** todo `scripts/migrate_*.py` que cria uma collection
**já inclui as regras de acesso no payload de criação** — nunca depende de um
PATCH posterior (o padrão do PocketBase é admin-only, o que exigiria liberar à
mão a cada migração). O padrão para collections novas é:

```python
"listRule": "", "viewRule": "",
"createRule": '@request.auth.id != ""',
"updateRule": '@request.auth.id != ""',
"deleteRule": '@request.auth.id != ""',
```

Exceções com regras próprias: `tentativas` (totalmente aberta — o modo público
grava/lê sem login), `users` (viewRule aberta a autenticados, mas create/update
admin-only) e `tokens_senha` (create/update públicos para o fluxo de redefinição
de senha).

> **Nota histórica:** `turmas`, `disciplinas`, `questoes`, `itens_vf`,
> `pares_associativos` e `atividades` foram seedadas **antes** de existir este
> código (não por um `scripts/migrate_*.py` deste repositório). O app cria/edita
> registros nessas collections usando o token de sessão do professor (nunca
> autentica como admin do PocketBase), então o `createRule`/`updateRule` real
> precisa aceitar esse token (equivalente a `@request.auth.id != ""`). Se uma
> collection especifica (ex: `itens_vf` para V/F) falhar com 403 enquanto
> `alternativas` funciona, é sinal de que ficou com uma regra mais restritiva —
> confirme em `/_/` → Collections → (nome) → API Rules. A importação de JSON
> expõe esse erro de forma legível (`_erro_http` em `app.py`): "permissão negada
> (403) — verifique as regras de acesso (createRule) da collection" em vez de
> uma exceção genérica.

---

## Autenticação e papéis (roles)

O login é feito via PocketBase JWT (`/api/collections/users/auth-with-password`). O token e o `role` do usuário são armazenados na sessão Flask.

| Role | Acesso |
|---|---|
| `aluno` | Portal, atividades, histórico, revisão |
| `professor` | Tudo do aluno + dashboard, gestão de turmas/disciplinas, bancos de questões e materiais, atividades (inclui multidisciplinar e importação JSON) e correção |
| `admin` | Igual ao professor |

O decorador `@requer_professor` bloqueia acesso a rotas `/professor/*` para usuários com `role="aluno"` e redireciona não autenticados para `/login`.

Em testes (`LOGIN_REQUIRED=False`), o decorador respeita o `role` da sessão — permitindo testar cenários de bloqueio sem autenticação real.

---

## Infraestrutura de produção

| Recurso | Valor |
|---|---|
| VM | Oracle Cloud — Ubuntu 22.04 — `147.15.54.41` |
| Domínio base | `repoept.duckdns.org` |
| PocketBase | `https://pb.repoept.duckdns.org` (porta 8090) |
| Flask LeDuk | `https://leduk.repoept.duckdns.org` (porta 8091) |
| Admin PocketBase | `https://pb.repoept.duckdns.org/_/` |
| Health check | `https://leduk.repoept.duckdns.org/health` |
| Banco SQLite | `/opt/pocketbase/pb_data/data.db` |
| App Flask | `/opt/leduk/` |

### Serviços systemd

```bash
sudo systemctl status pocketbase
sudo systemctl status leduk
sudo systemctl status nginx

journalctl -u pocketbase -f
journalctl -u leduk -f
```

### Gunicorn e factory `create_app()`

O `app.py` usa o padrão factory. O Gunicorn **não** encontra um atributo `app` direto — a configuração correta fica em `gunicorn.conf.py`:

```python
bind    = "127.0.0.1:8091"
workers = 2
wsgi_app = "app:create_app()"
```

### Deploy

```bash
bash /opt/leduk/deploy.sh
```

O script executa: `git pull` → `pip install` → corrige ExecStart → `systemctl restart leduk` → `curl /health`.

### Setup do zero

```bash
curl -O https://repoept.duckdns.org/repo/setup-leduk-completo.sh
chmod +x setup-leduk-completo.sh
./setup-leduk-completo.sh
```

---

## API PocketBase — referência rápida

### Autenticação admin

O token JWT expira em ~30 minutos. **Sempre reautenticar no início de cada bloco de operações.**

```bash
TOKEN=$(curl -s -X POST https://pb.repoept.duckdns.org/api/admins/auth-with-password \
  -H "Content-Type: application/json" \
  -d "{\"identity\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
```

### Inserções em lote — usar Python, não bash

Caracteres Unicode como `→` dentro de strings bash são interpretados pelo shell como redirecionamento de saída, corrompendo silenciosamente os dados. Para inserções em lote, **sempre usar Python**:

```python
import requests
headers = {"Authorization": TOKEN}
requests.post(f"{PB}/api/collections/alternativas/records",
    headers=headers,
    json={"questao": questao_id, "letra": "A", "texto": "Texto com acentos",
          "correta": False, "feedback": "Feedback da alternativa"})
```

---

## Dados de teste ativos

Registros seed presentes na instância de produção para validação do fluxo completo:

| Entidade | Nome | ID |
|---|---|---|
| Turma | 5TACN1 PROEJA | `z4brq8v61otdx5u` |
| Disciplina | IATS | `slip1kmh6zuxnxp` |
| Atividade | LIS | `h4if2m9rcywllur` |
| Questão mc5 | Fases do LIS | `zouibbp2kcmxkp7` |
| Questão mc5 | Conformidade | `vtpl1lyp4x1rd27` |
| Questão mc5 | Coleta e triagem | `vgx9b5jyxspov73` |
| Questão vf | Conceitos gerais | `bnom03jg46ldggk` |

URL de teste direto: `https://leduk.repoept.duckdns.org/atividade/h4if2m9rcywllur`

---

## Checklist de deploy

- [ ] PocketBase respondendo: `curl http://127.0.0.1:8090/api/health`
- [ ] Flask respondendo: `curl http://127.0.0.1:8091/health`
- [ ] Collections existem com `listRule`/`viewRule` vazias nas públicas (ver "Regras de acesso")
- [ ] Campo `atividade` existe em `tentativas`; campos `assunto` em `questoes`/`materiais`;
      campo `multidisciplinar` em `atividades` — já garantidos em produção (ver "Migrações históricas")
- [ ] Collection `turma_materiais` criada e com backfill rodado (`scripts/migrate_materiais.py`)
- [ ] Collections `boletins`, `unidades`, `recuperacao_final` criadas (`scripts/migrate_boletim.py`)
- [ ] Collections `tokens_senha` e `matriculas` criadas (`scripts/migrate_tokens_senha.py`, `scripts/migrate_matriculas.py`)
- [ ] Collection `formularios_cadastro` criada + campo `matricula` em `users` (`scripts/migrate_formulario_cadastro.py`)
- [ ] **Modo público:** campos `publica`/`descricao` em `turmas` e `aluno_email`/`aluno_turma`
      em `tentativas` (`scripts/migrate_turmas_publicas.py`); `questao` e `aluno_id` opcionais
      em `tentativas` (`scripts/migrate_tentativas_questao_optional.py`); rodar
      `python scripts/verificar_modo_publico.py --fix` para conferir campos + regras + testar
      um POST anônimo real
- [ ] `users`: `viewRule` aberta a autenticados (`@request.auth.id != ""`) para o `expand=aluno`
      em `matriculas` mostrar nome/email em vez do ID bruto
- [ ] Collections `templates_prova` e `provas` criadas (`scripts/migrate_provas.py`) — gerador de provas impressas
- [ ] `RESEND_API_KEY` definido no service (`/etc/systemd/system/leduk.service`) para envio de email
- [ ] `PB_PUBLIC_URL` definido no service (ex: `https://pb.repoept.duckdns.org`) para URLs públicas de arquivos de materiais
- [ ] `materiais`: `createRule`/`updateRule` = `@request.auth.id != ""` (necessário para upload multipart)
- [ ] Campo `correta` em `alternativas` com `required: false`
- [ ] Cada questão mc tem pelo menos uma alternativa com `correta: true`
- [ ] Gunicorn usando `app:create_app()` e não `app:app`
- [ ] Token PocketBase válido antes de cada bloco de operações

---

## Roadmap

| Etapa | Status | Descrição |
|---|---|---|
| 1 — Infraestrutura | Concluída | PocketBase, Flask/Gunicorn, Nginx, SSL |
| 2 — Schema | Concluída | 9 collections criadas com IDs fixos |
| 3 — Motor de atividades | Concluída | Rotas Flask + HTMX + validação de respostas |
| 4 — Autenticação | Concluída | Login JWT, roles, middleware, retomada de atividade |
| 5 — Portal do professor | Concluída | Dashboard + gestão de atividades + correção + liberação de notas |
| 6 — Pontuação por peso | Concluída | valor_total, peso por questão, nota_final, mapa de calor |
| 7 — Banco de questões | Concluída | CRUD completo mc4/mc5/vf/aberta/associativa + upload de imagem |
| 8 — Banco reutilizável | Concluída | Questões compartilhadas por disciplina: campo `assunto`, filtros, clonar, reclassificar, seletor para reuso entre atividades |
| 9 — Navegação do professor | Concluída | Menu hambúrguer dedicado (turmas + disciplinas + atalho ao banco), atalhos ao banco no dashboard e na turma |
| 10 — Gestão escolar completa | Concluída | CRUD de turmas/disciplinas (exclusão com confirmação + cascade), vínculo turma↔disciplina, banco de materiais reutilizável por disciplina (`turma_materiais`) |
| 11 — Banco geral e multidisciplinar | Concluída | Banco geral de questões (filtros cross-disciplina), montagem de atividade multidisciplinar e aba dedicada "Multidisciplinar" no portal do aluno |
| 12 — Importação JSON | Concluída | Importar questões via JSON (colar ou arquivo .json), com imagens por URL ou base64; arquivo de exemplo cobrindo todos os tipos |
| 13 — Boletim | Concluída | Boletim por turma: unidades por disciplina, recuperação de unidade e final, mapa de calor, relatório, situação (aprovado/recuperação/reprovado) e visão liberável ao aluno |
| 14 — Email + reset de senha | Concluída | Envio via Resend (boas-vindas, redefinição), token seguro (`secrets`, expira 24h, uso único), gestão e cadastro manual de alunos por turma |
| 15 — Auto-cadastro público | Concluída | Link de convite por turma (`/cadastro/<token>`), auto-cadastro com login automático, relatório + CSV, matrícula editável inline |
| 16 — Confiabilidade e UX do portal | Concluída | Histórico do aluno simplificado (uma linha por atividade + data da última tentativa), progresso "X de N respondidas" persistido corretamente, badge de tentativas restantes, exclusão de turma com cascade + confirmação explícita em vez de bloqueio simples |
| 17 — Modo público de atividades | Concluída | Turmas públicas sem matrícula (`/publica/<id>`), respondente identificado por nome/email (sem conta), limite de tentativas por email, gestão dedicada no painel do professor, comprovante individual com detalhamento por questão (mc/vf/associativa/aberta) e relatório geral — ambos impressos/salvos em PDF pelo navegador, badge visual "🌐 Pública" |
| 18 — Provas impressas | Concluída | Gerador de provas em papel a partir do banco de questões: seletor HTMX (adicionar/remover/reordenar com persistência imediata), templates de cabeçalho reutilizáveis, layout de impressão em 2 colunas com associativa em largura total e gabarito automático numa página separada, embaralhamento de questões e da coluna B de associativas com seed determinístico |

### Funcionalidades futuras consideradas

- Ingestão de PDFs com OCR + classificação via Claude API
- Repositório aberto de materiais didáticos (REA) no MinIO
- Geração automática de `.h5p` a partir do banco de questões
- Monitoramento via Uptime Kuma
- Anki Sync Server para flashcards de repetição espaçada
