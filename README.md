# LeDuk

Plataforma de atividades educacionais interativas self-hosted, construída sobre PocketBase + Flask + HTMX. Desenvolvida para o CETEP/LNAB (Alagoinhas, BA) com turmas EMI e PROEJA do curso Técnico em Análises Clínicas.

---

## Estrutura do repositório

```
leduk/
├── app.py                  ← aplicação Flask (factory create_app)
├── questao.py              ← lógica de validação e cálculo de score
├── pb.py                   ← cliente HTTP para o PocketBase
├── requirements.txt        ← dependências de produção
├── requirements-dev.txt    ← dependências de desenvolvimento (pytest etc.)
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
└── tests/
    ├── conftest.py             ← fixtures compartilhadas (app, client, questões)
    ├── fixtures/
    │   ├── questao_mc4.json
    │   ├── questao_vf.json
    │   └── questao_associativa.json
    ├── unit/
    │   ├── test_questao.py     ← validação de respostas mc / vf / associativa
    │   └── test_score.py       ← calcular_score para todos os tipos
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

**Resultado esperado:** 31 testes, todos passando.

---

## Rotas Flask

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/` | Home com lista de turmas |
| GET | `/atividade/<id>` | Shell da atividade (inicia fila de questões) |
| GET | `/htmx/questao/<id>` | Fragmento HTML da questão |
| POST | `/htmx/responder` | Valida resposta e retorna feedback |
| GET | `/htmx/proxima/<ativ_id>` | Fragmento da próxima questão |
| GET | `/htmx/resultado/<ativ_id>` | Placar final |
| GET | `/relatorio/turma/<id>` | Relatório agregado por turma |
| GET | `/relatorio/aluno/<id>` | Histórico individual |

### Fluxo HTMX

```
GET /atividade/<id>          ← carrega shell + primeira questão
        ↓
GET /htmx/questao/<id>       ← renderiza fragmento mc / vf / associativa
        ↓
POST /htmx/responder         ← valida resposta, grava tentativa no PocketBase
        ↓
_feedback.html               ← exibe correto/incorreto + feedback
        ↓
GET /htmx/proxima/<ativ_id>  ← próxima questão (repete até o fim)
        ↓
GET /htmx/resultado/<id>     ← placar final
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

| Collection | ID fixo | Descrição |
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
7. Criação das 9 collections com IDs fixos

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

```bash
curl -X POST https://pb.repoept.duckdns.org/api/admins/auth-with-password \
  -H "Content-Type: application/json" \
  -d '{"identity":"email@exemplo.com","password":"senha"}'
```

### Criar questão mc5

```bash
curl -X POST https://pb.repoept.duckdns.org/api/collections/questoes/records \
  -H "Authorization: Bearer TOKEN" \
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
  -H "Authorization: Bearer TOKEN" \
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
  -H "Authorization: Bearer TOKEN" \
  -F "enunciado=Identifique a morfologia:" \
  -F "tipo=mc4" \
  -F "disciplina=ID_DISCIPLINA" \
  -F "imagem=@hemacia-falciforme.jpg"
```

### Buscar questões por disciplina

```bash
curl "https://pb.repoept.duckdns.org/api/collections/questoes/records\
?filter=(disciplina='ID'%26%26tipo='mc5')&sort=-created&perPage=20" \
  -H "Authorization: Bearer TOKEN"
```

---

## Roadmap

| Etapa | Status | Descrição |
|---|---|---|
| 1 — Infraestrutura | Concluída | PocketBase, Flask/Gunicorn, Nginx, SSL |
| 2 — Schema | Concluída | 9 collections criadas com IDs fixos |
| 3 — Motor de atividades | Em andamento | Rotas Flask + HTMX + validação de respostas |
| 4 — Autenticação | Pendente | Login JWT, middleware, retomada de atividade |
| 5 — Relatórios | Pendente | Dashboard professor, PDF/Excel, taxa de erro |

### Funcionalidades futuras consideradas

- Ingestão de PDFs com OCR + classificação via Claude API
- Repositório aberto de materiais didáticos (REA) no MinIO
- Geração automática de `.h5p` a partir do banco de questões
- Monitoramento via Uptime Kuma
- Anki Sync Server para flashcards de repetição espaçada
