# LeDuk

Plataforma de atividades educacionais interativas self-hosted, construída sobre PocketBase + Flask + HTMX. Desenvolvida para o CETEP/LNAB (Alagoinhas, BA) com turmas EMI e PROEJA do curso Técnico em Análises Clínicas.

---

## Estrutura do repositório

```
leduk/
├── app.py                  ← aplicação Flask (factory create_app)
├── questao.py              ← lógica de validação e cálculo de score/nota
├── pb.py                   ← cliente HTTP para o PocketBase
├── gunicorn.conf.py        ← bind, workers, wsgi_app = "app:create_app()"
├── deploy.sh               ← pull → pip install → restart → health check
├── requirements.txt        ← dependências de produção
├── requirements-dev.txt    ← pytest, pytest-flask, responses
├── pytest.ini
│
├── scripts/
│   └── migrate_tentativas.py   ← migração: adiciona campo atividade ao schema
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
│   │   └── _toggle_ativa.html
│   ├── quiz/
│   │   └── shell.html
│   ├── aluno/
│   │   ├── historico.html
│   │   └── revisao.html
│   ├── turma/
│   │   └── portal.html
│   ├── professor/
│   │   ├── dashboard.html
│   │   ├── turma.html           ← lista com excluir/clonar/copiar link
│   │   ├── atividade_form.html
│   │   ├── questoes.html        ← banco de questões da atividade
│   │   ├── questao_form.html    ← criar/editar questão (todos os tipos + imagem)
│   │   ├── notas.html
│   │   └── notas_abertas.html
│   └── relatorio/
│       ├── turma.html
│       └── aluno.html
│
├── static/css/base.css     ← identidade visual + temas por disciplina
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
    │   └── test_peso.py
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
        └── test_gestao_atividade.py  ← smoke tests: excluir/clonar/CRUD questões
```

---

## Stack técnico

| Componente | Tecnologia |
|---|---|
| API + banco + auth | PocketBase 0.22.20 (SQLite embutido) |
| Backend | Flask 3.x + Gunicorn (2 workers) |
| Frontend | HTMX 1.9.12 (fragmentos HTML, sem SPA) |
| PDF | WeasyPrint |
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

**Resultado esperado:** 110 testes, todos passando.

---

## Rotas Flask

### Autenticação

| Método | Rota | Descrição |
|---|---|---|
| GET/POST | `/login` | Formulário de login via PocketBase JWT |
| GET | `/logout` | Limpa sessão e redireciona |

### Aluno

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/` | Home com atividades agrupadas por turma |
| GET | `/turma/<id>` | Portal da turma (disciplinas, atividades, materiais) |
| GET | `/atividade/<id>` | Shell da atividade (inicia fila de questões) |
| GET | `/htmx/questao/<id>` | Fragmento HTML da questão |
| POST | `/htmx/responder` | Valida resposta e retorna feedback |
| GET | `/htmx/proxima/<ativ_id>` | Fragmento da próxima questão |
| GET | `/htmx/resultado/<ativ_id>` | Placar final |
| GET | `/aluno/historico` | Histórico de tentativas do aluno |
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
| GET | `/professor/disciplina/<id>/banco-questoes` | Banco reutilizável da disciplina (filtros + uso) |
| GET/POST | `/professor/disciplina/<id>/questao/nova` | Criar questão direto no banco da disciplina |
| GET | `/professor/atividade/<id>/notas` | Notas dos alunos com liberação em lote |
| POST | `/professor/atividade/<id>/liberar-notas` | Liberar notas selecionadas |
| GET | `/professor/atividade/<id>/notas-abertas` | Corrigir questões abertas |
| POST | `/professor/questao-aberta/<tent_id>/avaliar` | Gravar nota de questão aberta |

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
| turmas | `0xiasmpkvxqig9c` | Turmas (EMI / PROEJA / FIC / EJA) |
| disciplinas | `m7urzbvhokcqdz0` | Disciplinas com cor e ícone por tema |
| turma_disciplina | `503sn0usao2qvp9` | Pivô N:N turma ↔ disciplina |
| questoes | `sdtq4w1im9dunfw` | Banco central de questões + imagem |
| alternativas | `jf69g6b4qr80hq3` | Opções mc4/mc5 com feedback e imagem |
| itens_vf | `dkc5b8csbsus7es` | Afirmações V/F ordenadas |
| pares_associativos | `8okcm31re6gxm4p` | Coluna A : Coluna B com imagens |
| tentativas | `2cgvat5j77ne31y` | Log completo de respostas por aluno |
| atividades | `44qehlo0jku49lq` | Agrupador de questões por turma/disciplina |

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

O campo `atividade` (relation → `atividades`) é obrigatório em ambos. Para migrar registros legados que usavam o campo `disciplina`:

```bash
PB_URL=https://pb.repoept.duckdns.org \
PB_ADMIN_EMAIL=admin@exemplo.com \
PB_ADMIN_PASSWORD=senha \
  python scripts/migrate_tentativas.py
```

### Diagrama de relacionamentos

```
turmas ──── turma_disciplina ──── disciplinas
                                       │
                                   questoes
                                  (mc4/mc5/vf/aberta/assoc)
                                       │
                    ┌──────────────────┼───────────────────┐
                    │                  │                   │
              alternativas         itens_vf     pares_associativos
              (A/B/C/D/E)       (afirmações)    (col_A : col_B)

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
8. tentativas         (depende de turmas + disciplinas + questoes)
9. atividades         (depende de turmas + disciplinas + questoes)
```

### Campos `bool` nunca devem ser `required: true`

O PocketBase trata `false` como valor vazio em campos bool obrigatórios e rejeita a inserção com `validation_required`. Sempre usar `"required": false` em campos bool.

### Regras de acesso (listRule / viewRule)

| Collection | listRule | viewRule | createRule | Observação |
|---|---|---|---|---|
| turmas | `""` | `""` | admin | leitura pública |
| disciplinas | `""` | `""` | admin | leitura pública |
| questoes | `""` | `""` | admin | leitura pública |
| alternativas | `""` | `""` | `""` | leitura + escrita pública (seed) |
| itens_vf | `""` | `""` | admin | leitura pública |
| atividades | `""` | `""` | admin | leitura pública |
| tentativas | restrito | restrito | `""` | apenas escrita pública |

---

## Autenticação e papéis (roles)

O login é feito via PocketBase JWT (`/api/collections/users/auth-with-password`). O token e o `role` do usuário são armazenados na sessão Flask.

| Role | Acesso |
|---|---|
| `aluno` | Portal, atividades, histórico, revisão |
| `professor` | Tudo do aluno + dashboard professor, gestão de atividades, correção |
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
- [ ] Collections existem com `listRule`/`viewRule` vazias nas públicas
- [ ] Campo `atividade` existe na collection `tentativas` (relation → atividades)
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

### Funcionalidades futuras consideradas

- Ingestão de PDFs com OCR + classificação via Claude API
- Repositório aberto de materiais didáticos (REA) no MinIO
- Geração automática de `.h5p` a partir do banco de questões
- Monitoramento via Uptime Kuma
- Anki Sync Server para flashcards de repetição espaçada
