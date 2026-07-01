#!/usr/bin/env python3
"""Migração: cria a collection `tokens_senha` (redefinição de senha).

Idempotente. Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_tokens_senha.py
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")


def _headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


def autenticar_admin() -> str:
    resp = requests.post(f"{PB_URL}/api/admins/auth-with-password",
                         json={"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    resp.raise_for_status()
    return resp.json()["token"]


def existe(token: str, name: str) -> bool:
    r = requests.get(f"{PB_URL}/api/collections/{name}", headers=_headers(token))
    return r.status_code == 200


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)
    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    if existe(token, "tokens_senha"):
        print("[OK] Collection 'tokens_senha' já existe.")
        return

    payload = {
        "name": "tokens_senha",
        "type": "base",
        "listRule": "",
        "viewRule": "",
        "createRule": "",
        "updateRule": "",
        "deleteRule": '@request.auth.id != ""',
        "schema": [
            {"name": "aluno_id", "type": "text", "required": True},
            {"name": "token", "type": "text", "required": True},
            {"name": "expira_em", "type": "date", "required": True},
            {"name": "usado", "type": "bool", "required": False},
        ],
    }
    r = requests.post(f"{PB_URL}/api/collections", headers=_headers(token), json=payload)
    r.raise_for_status()
    print("[OK] Collection 'tokens_senha' criada.")


if __name__ == "__main__":
    main()
