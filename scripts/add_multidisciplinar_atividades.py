#!/usr/bin/env python3
"""Migração: adiciona o campo booleano `multidisciplinar` à collection atividades.

Atividades com `multidisciplinar=true` aparecem na aba dedicada "Multidisciplinar"
do portal do aluno (e não na aba da disciplina principal). Idempotente.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/add_multidisciplinar_atividades.py
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")
ATIVIDADES_COL = os.environ.get("PB_ATIVIDADES_COLLECTION", "atividades")

CAMPO = {"name": "multidisciplinar", "type": "bool", "required": False}


def _headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


def autenticar_admin() -> str:
    resp = requests.post(
        f"{PB_URL}/api/admins/auth-with-password",
        json={"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["token"]


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    resp = requests.get(f"{PB_URL}/api/collections/{ATIVIDADES_COL}", headers=_headers(token))
    resp.raise_for_status()
    col = resp.json()
    schema = col.get("schema", [])
    if any(f["name"] == "multidisciplinar" for f in schema):
        print("[OK] Campo 'multidisciplinar' já existe — nada a fazer.")
        return

    schema.append(CAMPO)
    patch = requests.patch(
        f"{PB_URL}/api/collections/{col['id']}",
        headers=_headers(token), json={"schema": schema},
    )
    patch.raise_for_status()
    print("[OK] Campo 'multidisciplinar' adicionado a atividades.")


if __name__ == "__main__":
    main()
