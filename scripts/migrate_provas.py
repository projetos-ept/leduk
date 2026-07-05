#!/usr/bin/env python3
"""Migração: cria as collections `templates_prova` e `provas`.

Gerador de provas impressas com gabarito: o professor monta uma prova a
partir do banco de questões (mesmo banco usado pelas atividades digitais),
reaproveitando um cabeçalho salvo (`templates_prova`) entre várias provas.

templates_prova — cabeçalhos reutilizáveis:
  nome, cabecalho_html, instrucoes, professor (dono)

provas — a prova salva:
  titulo, template (relation opcional para templates_prova), cabecalho_html
  e instrucoes (podem sobrescrever o que veio do template), questoes
  (relation múltipla para `questoes` — a ORDEM do array é a ordem de
  impressão/numeração), professor (dono), embaralhar (bool).

`questoes` e `users` já têm ID fixo conhecido (README "IDs fixos"), não
precisam ser resolvidos em runtime. `templates_prova` é criada primeiro
porque `provas.template` referencia seu ID.

Idempotente: pode ser executado múltiplas vezes sem efeitos colaterais.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_provas.py
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")

USERS_COL_ID = "_pb_users_auth_"
QUESTOES_COL_ID = "sdtq4w1im9dunfw"
AUTH_RULE = '@request.auth.id != ""'


def _headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


def autenticar_admin() -> str:
    resp = requests.post(
        f"{PB_URL}/api/admins/auth-with-password",
        json={"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["token"]


def get_collection(token: str, name: str) -> dict | None:
    r = requests.get(f"{PB_URL}/api/collections/{name}", headers=_headers(token))
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def criar_templates_prova(token: str) -> dict:
    col = get_collection(token, "templates_prova")
    if col:
        print("[OK] Collection 'templates_prova' já existe.")
        return col
    payload = {
        "name": "templates_prova",
        "type": "base",
        "listRule": "", "viewRule": "",
        "createRule": AUTH_RULE, "updateRule": AUTH_RULE, "deleteRule": AUTH_RULE,
        "schema": [
            {"name": "nome", "type": "text", "required": True},
            {"name": "cabecalho_html", "type": "text", "required": False},
            {"name": "instrucoes", "type": "text", "required": False},
            {"name": "professor", "type": "relation", "required": False,
             "options": {"collectionId": USERS_COL_ID, "maxSelect": 1, "cascadeDelete": False}},
        ],
    }
    r = requests.post(f"{PB_URL}/api/collections", headers=_headers(token), json=payload)
    r.raise_for_status()
    print("[OK] Collection 'templates_prova' criada.")
    return r.json()


def criar_provas(token: str, template_col_id: str) -> None:
    if get_collection(token, "provas"):
        print("[OK] Collection 'provas' já existe.")
        return
    payload = {
        "name": "provas",
        "type": "base",
        "listRule": "", "viewRule": "",
        "createRule": AUTH_RULE, "updateRule": AUTH_RULE, "deleteRule": AUTH_RULE,
        "schema": [
            {"name": "titulo", "type": "text", "required": True},
            {"name": "template", "type": "relation", "required": False,
             "options": {"collectionId": template_col_id, "maxSelect": 1, "cascadeDelete": False}},
            {"name": "cabecalho_html", "type": "text", "required": False},
            {"name": "instrucoes", "type": "text", "required": False},
            {"name": "questoes", "type": "relation", "required": False,
             "options": {"collectionId": QUESTOES_COL_ID, "maxSelect": 999, "cascadeDelete": False}},
            {"name": "professor", "type": "relation", "required": False,
             "options": {"collectionId": USERS_COL_ID, "maxSelect": 1, "cascadeDelete": False}},
            {"name": "embaralhar", "type": "bool", "required": False},
        ],
    }
    r = requests.post(f"{PB_URL}/api/collections", headers=_headers(token), json=payload)
    r.raise_for_status()
    print("[OK] Collection 'provas' criada.")


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    template_col = criar_templates_prova(token)
    criar_provas(token, template_col["id"])

    print("Migração concluída — gerador de provas impressas habilitado.")


if __name__ == "__main__":
    main()
