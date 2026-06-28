# LeDuk

Plataforma de atividades educacionais interativas self-hosted, construída sobre PocketBase + Flask + HTMX. Desenvolvida para o CETEP/LNAB (Alagoinhas, BA) com turmas EMI e PROEJA do curso Técnico em Análises Clínicas.

---

## Estrutura do repositório

```
leduk/
├── app.py                  ← aplicação Flask (factory create_app)
├── questao.py              ← lógica de validação e cálculo de score
├── pb.py                   ← cliente HTTP para o PocketBase
├── gunicorn.conf.py        ← bind, workers, wsgi_app = "app:create_app()"
├── deploy.sh               ← pull → pip install → restart → health check
├── requirements.txt        ← dependências de produção
├── requirements-dev.txt    ← pytest, pytest-flask, responses
├── pytest.ini
│
├── templates/
│   ├── index.html
│   ├── components/
│   │   ├── _questao_mc.html
│   │   ├── _questao_vf.html
│   │   ├── _questao_assoc.html
│   │   ├── _feedback.html
│   │   └── _placar.html
│   ├── quiz/
│   │   └── shell.html
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
    │   └── test_score.py
    └── integration/
        ├── test_rotas_atividade.py
        ├── test_rotas_htmx.py
        └── test_relatorios.py
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

**Resultado esperado:** 33 testes, todos passando.

---

## Rotas Flask

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/` | Home com atividades agrupadas por turma |
| GET | `/atividade/<id>` | Shell da atividade (inicia fila de questões) |
| GET | `/htmx/questao/<id>` | Fragmento HTML da questão |
| POST | `/htmx/responder` | Valida resposta e retorna feedback |
| GET | `/htmx/proxima/<ativ_id>` | Fragmento da próxima questão |
| GET | `/htmx/resultado/<ativ_id>` | Placar final |
| GET | `/relatorio/turma/<id>` | Relatório agregado por turma |
| GET | `/relatorio/aluno/<id>` | Histórico individual |

### Fluxo HTMX

```
GET /atividade/<id>          ← carrega shell + primeira questão via hx-trigger
        ↓
GET /htmx/questao/<id>       ← renderiza fragmento mc / vf / associativa
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
| `aberta` | Resposta dissertativa | questão |
| `associativa` | Pares coluna A : coluna B | imagem por par |

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
tentativas  → log de cada resposta (aluno, questão, correta, score)
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

Capturar IDs dinamicamente após cada criação:

```bash
ID_TURMAS=$(curl -s -X POST ".../api/collections" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"turmas",...}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

### Campos `bool` nunca devem ser `required: true`

O PocketBase trata `false` como valor vazio em campos bool obrigatórios e rejeita a inserção com `validation_required`. Sempre usar `"required": false` em campos bool:

```json
{"name": "correta",    "type": "bool", "required": false}
{"name": "ativa",      "type": "bool", "required": false}
{"name": "embaralhar", "type": "bool", "required": false}
```

### Regras de acesso (listRule / viewRule)

Collections criadas via API ficam com acesso restrito a admins por padrão. O Flask recebe HTTP 403 ao tentar listas turmas, questões e alternativas sem liberar as regras.

Liberar em lote logo após criar as collections:

```bash
for col in turmas disciplinas atividades questoes alternativas itens_vf pares_associativos; do
  ID=$(curl -s ".../api/collections/${col}" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  curl -s -X PATCH ".../api/collections/${ID}" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"listRule":"","viewRule":""}' > /dev/null
  echo "liberado: $col"
done
```

Regras por collection:

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

O `ExecStart` do service deve ser:
```
ExecStart=/opt/leduk/.venv/bin/gunicorn -c /opt/leduk/gunicorn.conf.py app:create_app()
```

O `deploy.sh` detecta e corrige o `ExecStart` automaticamente se ainda estiver com o padrão antigo `app:app`.

### Deploy

```bash
bash /opt/leduk/deploy.sh
```

O script executa: `git pull` → `pip install` → corrige ExecStart → `systemctl restart leduk` → `curl /health`.

**Atenção:** o setup cria arquivos localmente antes do primeiro `git pull`. Se o pull for bloqueado por arquivos não rastreados, usar:

```bash
git checkout -f HEAD -- . 2>/dev/null || true
git clean -fd --exclude=.venv 2>/dev/null || true
git pull origin main
```

Esse padrão já está embutido no `deploy.sh`.

### Setup do zero

```bash
curl -O https://repoept.duckdns.org/repo/setup-leduk-completo.sh
chmod +x setup-leduk-completo.sh
./setup-leduk-completo.sh
```

O script executa em ordem:
1. Checagem de portas 8090 e 8091
2. Instalação de dependências (Python 3.11, Nginx, Certbot)
3. PocketBase como serviço systemd
4. Estrutura Flask + venv + Gunicorn
5. Nginx com proxy para ambos os subdomínios
6. SSL via Certbot
7. Criação das 9 collections com IDs capturados dinamicamente

Para resetar antes de rodar novamente:

```bash
sudo systemctl stop leduk pocketbase
sudo rm -rf /opt/pocketbase /opt/leduk
sudo rm -f /etc/systemd/system/{pocketbase,leduk}.service
sudo rm -f /etc/nginx/sites-{available,enabled}/{pocketbase,leduk}
sudo systemctl daemon-reload && sudo systemctl reload nginx
```

### Consumo de RAM

| Serviço | RAM idle |
|---|---|
| PocketBase | ~35 MB |
| Flask + Gunicorn (2w) | ~80 MB |
| Nginx | ~10 MB |
| **Total** | **~125 MB** |

Objetivo: manter abaixo de 250 MB em produção.

---

## API PocketBase — referência rápida

### Autenticação

O token JWT expira em ~30 minutos. **Sempre reautenticar no início de cada bloco de operações**, nunca reutilizar token de sessão anterior.

```bash
TOKEN=$(curl -s -X POST https://pb.repoept.duckdns.org/api/admins/auth-with-password \
  -H "Content-Type: application/json" \
  -d "{\"identity\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

[ -z "$TOKEN" ] && echo "ERRO: autenticação falhou" && exit 1
echo "Token obtido: ${TOKEN:0:20}..."
```

### Inserções em lote — usar Python, não bash

Caracteres Unicode como `→` dentro de strings bash com escape manual são interpretados pelo shell como redirecionamento de saída, corrompendo silenciosamente os dados. Para inserções em lote, **sempre usar Python**:

```python
import requests

headers = {"Authorization": f"Bearer {TOKEN}"}

requests.post(f"{PB}/api/collections/alternativas/records",
    headers=headers,
    json={
        "questao":   questao_id,
        "letra":     "A",
        "texto":     "Texto sem risco de escape — acentos e símbolos funcionam normalmente",
        "correta":   False,
        "feedback":  "Feedback da alternativa"
    })
```

Se precisar de setas em textos, usar `->` ou `para` no lugar de `→`.

### Criar questão mc5

```bash
curl -X POST https://pb.repoept.duckdns.org/api/collections/questoes/records \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enunciado": "Qual Ig atravessa a barreira placentária?",
    "tipo": "mc5",
    "disciplina": "ID_DISCIPLINA",
    "dificuldade": "medio",
    "tags": "imunoglobulinas,placenta",
    "feedback_geral": "A IgG é a única Ig que atravessa a placenta."
  }'
```

### Criar alternativa

```bash
curl -X POST https://pb.repoept.duckdns.org/api/collections/alternativas/records \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "questao": "ID_QUESTAO",
    "letra": "A",
    "texto": "IgG",
    "correta": true,
    "feedback": "Correto. IgG é a única que atravessa a barreira placentária."
  }'
```

### Upload de imagem em questão

```bash
curl -X POST https://pb.repoept.duckdns.org/api/collections/questoes/records \
  -H "Authorization: Bearer $TOKEN" \
  -F "enunciado=Identifique a morfologia:" \
  -F "tipo=mc4" \
  -F "disciplina=ID_DISCIPLINA" \
  -F "imagem=@hemacia-falciforme.jpg"
```

### Buscar questões por disciplina

```bash
curl "https://pb.repoept.duckdns.org/api/collections/questoes/records\
?filter=(disciplina='ID'%26%26tipo='mc5')&sort=-created&perPage=20" \
  -H "Authorization: Bearer $TOKEN"
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

Verificar antes de qualquer deploy ou operação em produção:

- [ ] PocketBase respondendo: `curl http://127.0.0.1:8090/api/health`
- [ ] Flask respondendo: `curl http://127.0.0.1:8091/health`
- [ ] Collections existem: resposta com 10 items em `/api/collections?perPage=50`
- [ ] `listRule` e `viewRule` vazias nas collections públicas
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
| 4 — Autenticação | Pendente | Login JWT, middleware, retomada de atividade |
| 5 — Relatórios | Pendente | Dashboard professor, PDF/Excel, taxa de erro |

### Funcionalidades futuras consideradas

- Ingestão de PDFs com OCR + classificação via Claude API
- Repositório aberto de materiais didáticos (REA) no MinIO
- Geração automática de `.h5p` a partir do banco de questões
- Monitoramento via Uptime Kuma
- Anki Sync Server para flashcards de repetição espaçada
