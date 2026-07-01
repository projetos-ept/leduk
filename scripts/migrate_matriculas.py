#!/usr/bin/env python3
"""Migração: cria a collection `matriculas` (vínculo aluno ↔ turma).

Usada pela gestão de alunos do professor (cadastro manual) e pela listagem de
alunos da turma. Idempotente; resolve os IDs de users e turmas em runtime.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_matriculas.py
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")
AUTH_RULE = '@request.auth.id != ""'


def _headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


def autenticar_admin() -> str:
    resp = requests.post(f"{PB_URL}/api/admins/auth-with-password",
                         json={"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    resp.raise_for_status()
    return resp.json()["token"]


def get_collection(token: str, name: str) -> dict | None:
    r = requests.get(f"{PB_URL}/api/collections/{name}", headers=_headers(token))
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)
    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    if get_collection(token, "matriculas"):
        print("[OK] Collection 'matriculas' já existe.")
        return

    users = get_collection(token, "users")
    turmas = get_collection(token, "turmas")
    if not users or not turmas:
        print("[ERRO] collections 'users'/'turmas' não encontradas.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "name": "matriculas",
        "type": "base",
        "listRule": "",
        "viewRule": "",
        "createRule": AUTH_RULE,
        "updateRule": AUTH_RULE,
        "deleteRule": AUTH_RULE,
        "schema": [
            {"name": "aluno", "type": "relation", "required": True,
             "options": {"collectionId": users["id"], "maxSelect": 1, "cascadeDelete": True}},
            {"name": "turma", "type": "relation", "required": True,
             "options": {"collectionId": turmas["id"], "maxSelect": 1, "cascadeDelete": False}},
            {"name": "ativo", "type": "bool", "required": False},
            {"name": "origem", "type": "text", "required": False},
            {"name": "whatsapp", "type": "text", "required": False},
        ],
    }
    r = requests.post(f"{PB_URL}/api/collections", headers=_headers(token), json=payload)
    r.raise_for_status()
    print("[OK] Collection 'matriculas' criada.")


if __name__ == "__main__":
    main()
