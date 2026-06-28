#!/bin/bash
# ============================================================
# LeDuk · Setup Completo — Etapas 1 + 2
# Oracle VM Ubuntu 22.04 · repoept.duckdns.org
# Roda do zero: PocketBase + Flask + todas as collections
# ============================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info() { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
erro() { echo -e "${RED}[ERRO]${NC} $1"; exit 1; }

# ── Configurações — edite se necessário ──
PB_PORT=8090
FLASK_PORT=8091
PB_DIR="/opt/pocketbase"
APP_DIR="/opt/leduk"
PB_SUBDOMAIN="pb.repoept.duckdns.org"
APP_SUBDOMAIN="leduk.repoept.duckdns.org"
SYSTEM_USER="ubuntu"
PB_VERSION="0.22.20"

echo ""
echo "======================================================"
echo "  LeDuk · Setup Completo (Etapas 1 + 2)"
echo "======================================================"
echo ""

# ============================================================
# ETAPA 1 — INFRAESTRUTURA
# ============================================================
echo ""
echo "── ETAPA 1 · Infraestrutura ──────────────────────────"
echo ""

# ── Checagem de portas ──
check_port() {
  local port=$1
  if ss -tlnp | grep -q ":${port} "; then
    local proc=$(ss -tlnp | grep ":${port} " | awk '{print $NF}' | head -1)
    warn "Porta $port em uso: $proc"
    read -p "    Continuar? (s/N): " resp
    [[ "$resp" != "s" && "$resp" != "S" ]] && erro "Abortado."
  else
    ok "Porta $port disponível."
  fi
}

info "Verificando portas..."
check_port $PB_PORT
check_port $FLASK_PORT

# ── Dependências ──
info "Instalando dependências..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  curl wget unzip nginx certbot python3-certbot-nginx \
  python3.11 python3.11-venv python3-pip
ok "Dependências instaladas."

# ── PocketBase ──
info "Baixando PocketBase v${PB_VERSION}..."
PB_URL="https://github.com/pocketbase/pocketbase/releases/download/v${PB_VERSION}/pocketbase_${PB_VERSION}_linux_amd64.zip"
wget -q --show-progress "$PB_URL" -O /tmp/pocketbase.zip || \
  erro "Falha no download."
sudo mkdir -p "$PB_DIR/pb_data"
sudo unzip -oq /tmp/pocketbase.zip -d "$PB_DIR"
sudo chmod +x "$PB_DIR/pocketbase"
sudo chown -R "$SYSTEM_USER":"$SYSTEM_USER" "$PB_DIR"
rm /tmp/pocketbase.zip
ok "PocketBase instalado em $PB_DIR"

# ── Systemd PocketBase ──
info "Criando service pocketbase..."
sudo tee /etc/systemd/system/pocketbase.service > /dev/null << UNIT
[Unit]
Description=PocketBase — LeDuk
After=network.target

[Service]
Type=simple
User=${SYSTEM_USER}
WorkingDirectory=${PB_DIR}
ExecStart=${PB_DIR}/pocketbase serve \
    --http=127.0.0.1:${PB_PORT} \
    --dir=${PB_DIR}/pb_data
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable pocketbase
sudo systemctl start pocketbase
sleep 3
systemctl is-active --quiet pocketbase && ok "PocketBase rodando." || \
  erro "PocketBase não iniciou. Veja: journalctl -u pocketbase -n 30"

# ── Testa API ──
info "Testando API..."
sleep 2
HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
  "http://127.0.0.1:${PB_PORT}/api/health")
[ "$HTTP" = "200" ] && ok "API respondendo (HTTP $HTTP)." || \
  warn "API retornou HTTP $HTTP."

# ── Flask estrutura ──
info "Criando estrutura Flask em $APP_DIR..."
sudo mkdir -p "$APP_DIR"/{templates/{components,quiz,relatorio},static/{css,js},pb_hooks}
sudo chown -R "$SYSTEM_USER":"$SYSTEM_USER" "$APP_DIR"

info "Criando venv Python 3.11..."
python3.11 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q flask requests gunicorn weasyprint
ok "venv criado."

cat > "$APP_DIR/app.py" << 'PYEOF'
import os, requests
from flask import Flask, render_template, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-em-producao")
PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090")

def pb_get(collection, params=None):
    r = requests.get(f"{PB_URL}/api/collections/{collection}/records",
                     params=params or {})
    r.raise_for_status()
    return r.json()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    try:
        pb = requests.get(f"{PB_URL}/api/health", timeout=3).json()
        return jsonify({"flask": "ok", "pocketbase": pb})
    except Exception as e:
        return jsonify({"flask": "ok", "pocketbase": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=8091)
PYEOF

cat > "$APP_DIR/templates/index.html" << 'HTMLEOF'
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LeDuk</title>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <link rel="stylesheet" href="/static/css/base.css">
</head>
<body>
  <header>
    <span class="brand">LeDuk · Análises Clínicas</span>
  </header>
  <main>
    <p>Etapa 1 concluída.</p>
    <div hx-get="/health" hx-trigger="load" hx-swap="innerHTML">
      verificando serviços...
    </div>
  </main>
</body>
</html>
HTMLEOF

cat > "$APP_DIR/static/css/base.css" << 'CSSEOF'
:root {
  --bg:#0f1117; --surface:#181c27; --accent:#00c9a7;
  --text:#e2e8f0; --muted:#64748b;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:sans-serif;padding:2rem}
header{border-bottom:1px solid #252a38;padding-bottom:1rem;margin-bottom:2rem}
.brand{font-size:1.1rem;font-weight:600;color:var(--accent)}
CSSEOF

# ── Systemd Flask ──
info "Criando service leduk..."
sudo tee /etc/systemd/system/leduk.service > /dev/null << UNIT
[Unit]
Description=LeDuk — Flask
After=pocketbase.service network.target

[Service]
Type=simple
User=${SYSTEM_USER}
WorkingDirectory=${APP_DIR}
Environment="PB_URL=http://127.0.0.1:${PB_PORT}"
Environment="SECRET_KEY=$(openssl rand -hex 32)"
ExecStart=${APP_DIR}/.venv/bin/gunicorn \
    -w 2 -b 127.0.0.1:${FLASK_PORT} app:app \
    --access-logfile - --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable leduk
sudo systemctl start leduk
sleep 3
systemctl is-active --quiet leduk && ok "Flask rodando na porta $FLASK_PORT." || \
  warn "Flask não iniciou. Veja: journalctl -u leduk -n 30"

# ── Nginx ──
info "Configurando Nginx..."
sudo tee /etc/nginx/sites-available/pocketbase > /dev/null << NGINX
server {
    listen 80;
    server_name ${PB_SUBDOMAIN};
    client_max_body_size 50M;
    location / {
        proxy_pass http://127.0.0.1:${PB_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
    }
}
NGINX

sudo tee /etc/nginx/sites-available/leduk > /dev/null << NGINX
server {
    listen 80;
    server_name ${APP_SUBDOMAIN};
    client_max_body_size 20M;
    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
    }
    location / {
        proxy_pass http://127.0.0.1:${FLASK_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/pocketbase /etc/nginx/sites-enabled/pocketbase
sudo ln -sf /etc/nginx/sites-available/leduk /etc/nginx/sites-enabled/leduk
sudo nginx -t && sudo systemctl reload nginx
ok "Nginx configurado."

# ── SSL ──
echo ""
read -p "Configurar SSL agora? (s/N): " ssl_resp
if [[ "$ssl_resp" == "s" || "$ssl_resp" == "S" ]]; then
  sudo certbot --nginx \
    -d "$PB_SUBDOMAIN" -d "$APP_SUBDOMAIN" \
    --non-interactive --agree-tos \
    -m "lucas.batista.eduk@gmail.com" && ok "SSL configurado." || \
    warn "Certbot falhou — rode manualmente depois."
else
  warn "SSL pendente. Rode: sudo certbot --nginx -d $PB_SUBDOMAIN -d $APP_SUBDOMAIN"
fi

# ── Saúde pós etapa 1 ──
echo ""
info "Health check Etapa 1:"
sleep 2
curl -s "http://127.0.0.1:${FLASK_PORT}/health" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  print(f'  flask: {d[\"flask\"]}  |  pocketbase: {d[\"pocketbase\"].get(\"message\",\"?\")}')"

# ============================================================
# ETAPA 2 — COLLECTIONS POCKETBASE
# ============================================================
echo ""
echo "── ETAPA 2 · Collections PocketBase ─────────────────"
echo ""
echo "  Acesse https://${PB_SUBDOMAIN}/_/ e crie o admin"
echo "  antes de continuar."
echo ""
read -p "  Email admin PocketBase: " PB_EMAIL
read -s -p "  Senha admin PocketBase: " PB_PASS
echo ""

info "Autenticando no PocketBase..."
AUTH=$(curl -s -X POST "http://127.0.0.1:${PB_PORT}/api/admins/auth-with-password" \
  -H "Content-Type: application/json" \
  -d "{\"identity\":\"${PB_EMAIL}\",\"password\":\"${PB_PASS}\"}")
TOKEN=$(echo "$AUTH" | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null)
[ -z "$TOKEN" ] && erro "Autenticação falhou. Verifique email/senha."
ok "Token obtido."

# ── Função criar collection e retornar ID ──
create_col() {
  local name=$1
  local payload=$2
  info "Criando: $name..."
  RESP=$(curl -s -X POST "http://127.0.0.1:${PB_PORT}/api/collections" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$payload")
  local id
  id=$(echo "$RESP" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
  if [ -n "$id" ] && [ "$id" != "None" ]; then
    ok "$name criada. ID: $id"
    echo "$id"
  else
    local msg
    msg=$(echo "$RESP" | python3 -c \
      "import sys,json; print(json.load(sys.stdin).get('message','?'))" 2>/dev/null)
    warn "$name falhou: $msg"
    echo ""
  fi
}

# ── 1. turmas ──
ID_TURMAS=$(create_col "turmas" '{
  "name":"turmas","type":"base","schema":[
    {"name":"nome",       "type":"text",  "required":true},
    {"name":"modalidade", "type":"select","required":true,
     "options":{"maxSelect":1,"values":["EMI","PROEJA","FIC","EJA"]}},
    {"name":"ano",        "type":"number","required":false},
    {"name":"ativa",      "type":"bool",  "required":false}
  ]
}')

# ── 2. disciplinas ──
ID_DISCIPLINAS=$(create_col "disciplinas" '{
  "name":"disciplinas","type":"base","schema":[
    {"name":"nome",      "type":"text","required":true},
    {"name":"codigo",    "type":"text","required":false},
    {"name":"cor_tema",  "type":"text","required":false},
    {"name":"icone",     "type":"text","required":false},
    {"name":"ativa",     "type":"bool","required":false}
  ]
}')

[ -z "$ID_TURMAS" ] && erro "turmas não criada — abortando."
[ -z "$ID_DISCIPLINAS" ] && erro "disciplinas não criada — abortando."

# ── 3. turma_disciplina ──
create_col "turma_disciplina" "{
  \"name\":\"turma_disciplina\",\"type\":\"base\",\"schema\":[
    {\"name\":\"turma\",      \"type\":\"relation\",\"required\":true,
     \"options\":{\"collectionId\":\"${ID_TURMAS}\",\"maxSelect\":1,\"cascadeDelete\":false}},
    {\"name\":\"disciplina\", \"type\":\"relation\",\"required\":true,
     \"options\":{\"collectionId\":\"${ID_DISCIPLINAS}\",\"maxSelect\":1,\"cascadeDelete\":false}},
    {\"name\":\"professor\",  \"type\":\"text\",\"required\":false},
    {\"name\":\"semestre\",   \"type\":\"text\",\"required\":false}
  ]
}" > /dev/null

# ── 4. questoes ──
ID_QUESTOES=$(create_col "questoes" "{
  \"name\":\"questoes\",\"type\":\"base\",\"schema\":[
    {\"name\":\"enunciado\",     \"type\":\"text\",   \"required\":true},
    {\"name\":\"tipo\",          \"type\":\"select\", \"required\":true,
     \"options\":{\"maxSelect\":1,\"values\":[\"mc4\",\"mc5\",\"vf\",\"aberta\",\"associativa\"]}},
    {\"name\":\"disciplina\",    \"type\":\"relation\",\"required\":true,
     \"options\":{\"collectionId\":\"${ID_DISCIPLINAS}\",\"maxSelect\":1,\"cascadeDelete\":false}},
    {\"name\":\"dificuldade\",   \"type\":\"select\", \"required\":false,
     \"options\":{\"maxSelect\":1,\"values\":[\"facil\",\"medio\",\"dificil\"]}},
    {\"name\":\"tags\",          \"type\":\"text\",   \"required\":false},
    {\"name\":\"imagem\",        \"type\":\"file\",   \"required\":false,
     \"options\":{\"maxSelect\":1,\"maxSize\":5242880,
       \"mimeTypes\":[\"image/jpeg\",\"image/png\",\"image/webp\",\"image/gif\"]}},
    {\"name\":\"imagem_legenda\",\"type\":\"text\",   \"required\":false},
    {\"name\":\"feedback_geral\",\"type\":\"text\",   \"required\":false},
    {\"name\":\"ativa\",         \"type\":\"bool\",   \"required\":false}
  ]
}")

[ -z "$ID_QUESTOES" ] && erro "questoes não criada — abortando."

# ── 5. alternativas ──
create_col "alternativas" "{
  \"name\":\"alternativas\",\"type\":\"base\",\"schema\":[
    {\"name\":\"questao\", \"type\":\"relation\",\"required\":true,
     \"options\":{\"collectionId\":\"${ID_QUESTOES}\",\"maxSelect\":1,\"cascadeDelete\":true}},
    {\"name\":\"letra\",   \"type\":\"select\", \"required\":true,
     \"options\":{\"maxSelect\":1,\"values\":[\"A\",\"B\",\"C\",\"D\",\"E\"]}},
    {\"name\":\"texto\",   \"type\":\"text\",   \"required\":true},
    {\"name\":\"correta\", \"type\":\"bool\",   \"required\":true},
    {\"name\":\"feedback\",\"type\":\"text\",   \"required\":false},
    {\"name\":\"imagem\",  \"type\":\"file\",   \"required\":false,
     \"options\":{\"maxSelect\":1,\"maxSize\":3145728,
       \"mimeTypes\":[\"image/jpeg\",\"image/png\",\"image/webp\"]}}
  ]
}" > /dev/null

# ── 6. itens_vf ──
create_col "itens_vf" "{
  \"name\":\"itens_vf\",\"type\":\"base\",\"schema\":[
    {\"name\":\"questao\",   \"type\":\"relation\",\"required\":true,
     \"options\":{\"collectionId\":\"${ID_QUESTOES}\",\"maxSelect\":1,\"cascadeDelete\":true}},
    {\"name\":\"ordem\",     \"type\":\"number\", \"required\":true},
    {\"name\":\"afirmacao\", \"type\":\"text\",   \"required\":true},
    {\"name\":\"gabarito\",  \"type\":\"bool\",   \"required\":true},
    {\"name\":\"feedback\",  \"type\":\"text\",   \"required\":false},
    {\"name\":\"imagem\",    \"type\":\"file\",   \"required\":false,
     \"options\":{\"maxSelect\":1,\"maxSize\":3145728,
       \"mimeTypes\":[\"image/jpeg\",\"image/png\",\"image/webp\"]}}
  ]
}" > /dev/null

# ── 7. pares_associativos ──
create_col "pares_associativos" "{
  \"name\":\"pares_associativos\",\"type\":\"base\",\"schema\":[
    {\"name\":\"questao\",  \"type\":\"relation\",\"required\":true,
     \"options\":{\"collectionId\":\"${ID_QUESTOES}\",\"maxSelect\":1,\"cascadeDelete\":true}},
    {\"name\":\"ordem\",    \"type\":\"number\", \"required\":true},
    {\"name\":\"coluna_a\", \"type\":\"text\",   \"required\":true},
    {\"name\":\"coluna_b\", \"type\":\"text\",   \"required\":true},
    {\"name\":\"imagem_a\", \"type\":\"file\",   \"required\":false,
     \"options\":{\"maxSelect\":1,\"maxSize\":3145728,
       \"mimeTypes\":[\"image/jpeg\",\"image/png\",\"image/webp\"]}},
    {\"name\":\"imagem_b\", \"type\":\"file\",   \"required\":false,
     \"options\":{\"maxSelect\":1,\"maxSize\":3145728,
       \"mimeTypes\":[\"image/jpeg\",\"image/png\",\"image/webp\"]}}
  ]
}" > /dev/null

# ── 8. tentativas ──
create_col "tentativas" "{
  \"name\":\"tentativas\",\"type\":\"base\",\"schema\":[
    {\"name\":\"aluno_id\",     \"type\":\"text\",    \"required\":true},
    {\"name\":\"aluno_nome\",   \"type\":\"text\",    \"required\":false},
    {\"name\":\"turma\",        \"type\":\"relation\",\"required\":false,
     \"options\":{\"collectionId\":\"${ID_TURMAS}\",\"maxSelect\":1,\"cascadeDelete\":false}},
    {\"name\":\"disciplina\",   \"type\":\"relation\",\"required\":false,
     \"options\":{\"collectionId\":\"${ID_DISCIPLINAS}\",\"maxSelect\":1,\"cascadeDelete\":false}},
    {\"name\":\"questao\",      \"type\":\"relation\",\"required\":true,
     \"options\":{\"collectionId\":\"${ID_QUESTOES}\",\"maxSelect\":1,\"cascadeDelete\":false}},
    {\"name\":\"tipo_questao\", \"type\":\"select\",  \"required\":false,
     \"options\":{\"maxSelect\":1,\"values\":[\"mc4\",\"mc5\",\"vf\",\"aberta\",\"associativa\"]}},
    {\"name\":\"resposta_dada\",\"type\":\"text\",    \"required\":false},
    {\"name\":\"correta\",      \"type\":\"bool\",    \"required\":false},
    {\"name\":\"duracao_seg\",  \"type\":\"number\",  \"required\":false},
    {\"name\":\"score_raw\",    \"type\":\"number\",  \"required\":false},
    {\"name\":\"score_max\",    \"type\":\"number\",  \"required\":false}
  ]
}" > /dev/null

# ── 9. atividades ──
create_col "atividades" "{
  \"name\":\"atividades\",\"type\":\"base\",\"schema\":[
    {\"name\":\"titulo\",       \"type\":\"text\",    \"required\":true},
    {\"name\":\"descricao\",    \"type\":\"text\",    \"required\":false},
    {\"name\":\"turma\",        \"type\":\"relation\",\"required\":true,
     \"options\":{\"collectionId\":\"${ID_TURMAS}\",\"maxSelect\":1,\"cascadeDelete\":false}},
    {\"name\":\"disciplina\",   \"type\":\"relation\",\"required\":true,
     \"options\":{\"collectionId\":\"${ID_DISCIPLINAS}\",\"maxSelect\":1,\"cascadeDelete\":false}},
    {\"name\":\"tipo\",         \"type\":\"select\",  \"required\":false,
     \"options\":{\"maxSelect\":1,\"values\":[\"avaliacao\",\"treino\",\"revisao\",\"diagnostico\"]}},
    {\"name\":\"questoes\",     \"type\":\"relation\",\"required\":false,
     \"options\":{\"collectionId\":\"${ID_QUESTOES}\",\"maxSelect\":999,\"cascadeDelete\":false}},
    {\"name\":\"embaralhar\",   \"type\":\"bool\",    \"required\":false},
    {\"name\":\"tempo_limite\", \"type\":\"number\",  \"required\":false},
    {\"name\":\"ativa\",        \"type\":\"bool\",    \"required\":false}
  ]
}" > /dev/null

# ── Verificação final ──
echo ""
info "Collections criadas:"
echo ""
curl -s "http://127.0.0.1:${PB_PORT}/api/collections?perPage=50" \
  -H "Authorization: Bearer ${TOKEN}" | \
  python3 -c "
import sys,json
items=json.load(sys.stdin).get('items',[])
print(f'  Total: {len(items)}')
for c in items:
    print(f'  ✓  {c[\"name\"]:30s} {c[\"id\"]}')
"

# ── RAM ──
echo ""
info "Consumo de RAM:"
for svc in pocketbase leduk nginx; do
  pid=$(systemctl show -p MainPID "$svc" 2>/dev/null | cut -d= -f2)
  if [[ -n "$pid" && "$pid" != "0" ]]; then
    rss=$(ps -o rss= -p "$pid" 2>/dev/null | \
      awk '{printf "%.0f MB", $1/1024}')
    printf "  %-20s %s\n" "$svc" "${rss:-n/d}"
  fi
done
echo ""
free -h | awk '/Mem:/{printf "  RAM: total %s  |  usado %s  |  livre %s\n",$2,$3,$4}'

echo ""
echo "======================================================"
echo "  SETUP COMPLETO"
echo "======================================================"
echo ""
echo "  PocketBase admin : https://${PB_SUBDOMAIN}/_/"
echo "  API PocketBase   : https://${PB_SUBDOMAIN}/api/"
echo "  LeDuk app        : https://${APP_SUBDOMAIN}/"
echo "  Health check     : https://${APP_SUBDOMAIN}/health"
echo ""
echo "  Banco SQLite     : ${PB_DIR}/pb_data/data.db"
echo "  Flask app        : ${APP_DIR}/app.py"
echo ""
echo "  Próximo → Etapa 3: Flask + HTMX · Motor de atividades"
echo "======================================================"
