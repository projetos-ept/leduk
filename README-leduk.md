# LeDuk

Plataforma de atividades educacionais interativas self-hosted, construída sobre PocketBase + Flask + HTMX. Desenvolvida para uso no CETEP/LNAB (Alagoinhas, BA) com turmas EMI e PROEJA do curso Técnico em Análises Clínicas.

---

## Infraestrutura

| Recurso | Valor |
|---|---|
| VM | Oracle Cloud — Ubuntu 22.04 — `147.15.54.41` |
| Domínio base | `repoept.duckdns.org` |
| PocketBase | `https://pb.repoept.duckdns.org` — porta `8090` |
| Flask LeDuk | `https://leduk.repoept.duckdns.org` — porta `8091` |
| Admin PocketBase | `https://pb.repoept.duckdns.org/_/` |
| Health check | `https://leduk.repoept.duckdns.org/health` |
| Banco SQLite | `/opt/pocketbase/pb_data/data.db` |
| App Flask | `/opt/leduk/` |
| Scripts de setup | `https://repoept.duckdns.org/repo/` |

### Serviços systemd

```bash
sudo systemctl status pocketbase   # PocketBase
sudo systemctl status leduk        # Flask + Gunicorn
sudo systemctl status nginx        # Proxy reverso
```

### Logs

```bash
journalctl -u pocketbase -f
journalctl -u leduk -f
```

---

## Stack técnico

```
PocketBase 0.22.20   → API REST + auth JWT + SQLite + file storage
Flask 3.x            → backend Python, rotas, templates, lógica
Gunicorn             → servidor WSGI (2 workers)
HTMX 1.9.12         → frontend reativo sem SPA, fragmentos HTML
WeasyPrint           → geração de PDF (relatórios)
Nginx                → proxy reverso + SSL (Let's Encrypt)
```

---

## Collections PocketBase

Todas as collections estão criadas e operacionais. IDs fixos:

| Collection | ID | Descrição |
|---|---|---|
| users | `_pb_users_auth_` | Alunos e professores (nativo PocketBase) |
| turmas | `0xiasmpkvxqig9c` | Turmas (EMI / PROEJA / FIC / EJA) |
| disciplinas | `m7urzbvhokcqdz0` | Disciplinas com cor e ícone por tema |
| turma_disciplina | `503sn0usao2qvp9` | Pivô N:N turma ↔ disciplina |
| questoes | `sdtq4w1im9dunfw` | Banco central de questões + imagem |
| alternativas | `jf69g6b4qr80hq3` | Opções mc4/mc5 com feedback e imagem |
| itens_vf | `dkc5b8csbsus7es` | Afirmações V/F ordenadas |
| pares_associativos | `8okcm31re6gxm4p` | Coluna A : Coluna B com imagens |
| tentativas | `2cgvat5j77ne31y` | Log completo de respostas por aluno |
| atividades | `44qehlo0jku49lq` | Agrupador de questões por turma/disciplina |

### Diagrama de relacionamentos

```
turmas ──────────────── turma_disciplina ──────────────── disciplinas
                                                               │
                                                           questoes
                                                          (mc4/mc5/vf/
                                                         aberta/assoc)
                                                               │
                                     ┌─────────────────────────┤
                                     │                         │
                               alternativas              itens_vf
                               (A/B/C/D/E)           (afirmações V/F)
                                     │
                             pares_associativos
                              (col_A : col_B)

atividades  → agrupa questoes por turma + disciplina
tentativas  → log de cada resposta por aluno
```

### Tipos de questão suportados

| Tipo | Descrição | Suporte a imagem |
|---|---|---|
| `mc4` | Múltipla escolha — 4 alternativas | questão + cada alternativa |
| `mc5` | Múltipla escolha — 5 alternativas | questão + cada alternativa |
| `vf` | Lista de afirmações V/F ordenadas | por afirmação |
| `aberta` | Resposta dissertativa | questão |
| `associativa` | Pares coluna A : coluna B | imagem por par (A e B) |

---

## Setup do zero

Script unificado que instala e configura tudo (Etapas 1 + 2):

```bash
curl -O https://repoept.duckdns.org/repo/setup-leduk-completo.sh
chmod +x setup-leduk-completo.sh
./setup-leduk-completo.sh
```

O script executa em ordem:
1. Checagem de portas 8090 e 8091
2. Instalação de dependências (Python 3.11, Nginx, Certbot)
3. Download e configuração do PocketBase como serviço systemd
4. Criação da estrutura Flask + venv + Gunicorn
5. Configuração Nginx com proxy para ambos os subdomínios
6. SSL via Certbot (opcional, interativo)
7. Autenticação no PocketBase e criação das 9 collections com IDs capturados dinamicamente

Para recomeçar do zero antes de rodar:

```bash
sudo systemctl stop leduk pocketbase
sudo rm -rf /opt/pocketbase /opt/leduk
sudo rm -f /etc/systemd/system/{pocketbase,leduk}.service
sudo rm -f /etc/nginx/sites-{available,enabled}/{pocketbase,leduk}
sudo systemctl daemon-reload && sudo systemctl reload nginx
```

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

### Registrar tentativa

```bash
curl -X POST https://pb.repoept.duckdns.org/api/collections/tentativas/records \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "aluno_id": "ID_ALUNO",
    "aluno_nome": "João Silva",
    "turma": "ID_TURMA",
    "disciplina": "ID_DISCIPLINA",
    "questao": "ID_QUESTAO",
    "tipo_questao": "mc5",
    "resposta_dada": "A",
    "correta": true,
    "duracao_seg": 45,
    "score_raw": 1,
    "score_max": 1
  }'
```

---

## Estrutura de arquivos Flask

```
/opt/leduk/
├── app.py                          ← entrada principal Flask
├── .venv/                          ← dependências Python isoladas
├── templates/
│   ├── index.html                  ← home (HTMX shell)
│   ├── components/
│   │   ├── _questao_mc.html        ← fragmento múltipla escolha
│   │   ├── _questao_vf.html        ← fragmento V/F
│   │   ├── _questao_assoc.html     ← fragmento associativa
│   │   ├── _feedback.html          ← caixa de feedback pós-resposta
│   │   ├── _progress.html          ← barra de progresso
│   │   └── _placar.html            ← resultado final
│   ├── quiz/
│   │   ├── mc.html                 ← página de quiz mc
│   │   ├── vf.html                 ← página de quiz vf
│   │   └── resultado.html          ← placar final
│   └── relatorio/
│       ├── turma.html              ← relatório por turma
│       └── aluno.html              ← histórico por aluno
├── static/
│   ├── css/
│   │   └── base.css                ← identidade visual LeDuk
│   └── js/
└── pb_hooks/                       ← hooks JS server-side PocketBase
```

---

## Roadmap — próximas etapas

### Etapa 3 — Flask + HTMX · Motor de atividades

Rotas a implementar:

```
GET  /                           → home com turmas e disciplinas
GET  /atividade/<id>             → shell da atividade (HTMX host)
GET  /htmx/questao/<id>          → fragmento HTML da questão atual
POST /htmx/responder             → valida resposta → retorna feedback
GET  /htmx/proxima/<id>          → fragmento da próxima questão
GET  /htmx/resultado/<ativ_id>   → placar final
```

Fluxo HTMX:

```
página shell carrega
      ↓
hx-get /htmx/questao/1 → renderiza questão
      ↓
aluno responde → hx-post /htmx/responder
      ↓
Flask valida + grava tentativa no PocketBase
      ↓
retorna fragmento _feedback.html
      ↓
hx-get /htmx/proxima → próxima questão
      ↓
(repete até fim) → /htmx/resultado
```

### Etapa 4 — Autenticação + sessão de aluno

- Login via PocketBase JWT (email/senha)
- Flask guarda token na sessão
- Middleware valida token antes de servir atividades
- Aluno pode retomar atividade interrompida

### Etapa 5 — Relatórios + painel do professor

```
GET /professor/dashboard              → visão geral das turmas
GET /htmx/relatorio/<turma>           → fragmento tabela de desempenho
GET /htmx/questoes/taxa-erro          → questões com maior índice de erro
GET /relatorio/<turma>/pdf            → PDF via WeasyPrint
GET /export/<turma>.xlsx              → exportação Excel via pandas
```

### Funcionalidades futuras consideradas

- Pipeline de ingestão de PDFs com OCR (Stirling-PDF) + classificação via Claude API
- Repositório aberto de materiais didáticos (REA) sobre o MinIO
- Geração automática de `.h5p` a partir do banco de questões
- Monitoramento de serviços via Uptime Kuma
- Anki Sync Server para flashcards de repetição espaçada

---

## Customização visual

O sistema não impõe tema — o visual é inteiramente controlado pelo Flask + Jinja2 + CSS. Suporte a tema por disciplina via variável de contexto:

```python
TEMAS = {
    "imunologia":    {"cor": "#00c9a7", "icone": "🧬"},
    "hematologia":   {"cor": "#ff6b6b", "icone": "🩸"},
    "microbiologia": {"cor": "#5b8dee", "icone": "🔬"},
    "bioquimica":    {"cor": "#f7b731", "icone": "⚗️"},
}
```

Templates separados por modalidade (EMI vs PROEJA) para adequar densidade e complexidade da interface ao público.

---

## Consumo de RAM

Referência pós-instalação com todos os serviços ativos:

| Serviço | RAM idle |
|---|---|
| PocketBase | ~35 MB |
| Flask + Gunicorn (2w) | ~80 MB |
| Nginx | ~10 MB |
| **Total estimado** | **~125 MB** |

Objetivo: manter abaixo de 250 MB com todos os serviços de produção rodando.
