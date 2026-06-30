#!/usr/bin/env python3
"""Migração: adiciona o campo 'assunto' (text) à collection questoes.

O campo é livre e opcional — usado para organizar e filtrar questões dentro do
banco de uma disciplina (ex: "Fases do LIS", "Imunoglobulinas").

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/add_assunto_questoes.py
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")
QUESTOES_COL = os.environ.get("PB_QUESTOES_COLLECTION", "questoes")

CAMPO_ASSUNTO = {
    "name": "assunto",
    "type": "text",
    "required": False,
}


def _headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


def autenticar_admin() -> str:
    resp = requests.post(
        f"{PB_URL}/api/admins/auth-with-password",
        json={"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["token"]


def get_collection(token: str, name: str) -> dict:
    resp = requests.get(f"{PB_URL}/api/collections/{name}", headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


def adicionar_campo_schema(token: str, collection: dict) -> None:
    schema = collection.get("schema", [])
    if any(f["name"] == "assunto" for f in schema):
        print("[OK] Campo 'assunto' já existe no schema — nada a fazer.")
        return

    schema.append(CAMPO_ASSUNTO)
    resp = requests.patch(
        f"{PB_URL}/api/collections/{collection['id']}",
        headers=_headers(token),
        json={"schema": schema},
    )
    resp.raise_for_status()
    print("[OK] Campo 'assunto' adicionado ao schema de questoes.")


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    collection = get_collection(token, QUESTOES_COL)
    adicionar_campo_schema(token, collection)
    print("Migração concluída.")


if __name__ == "__main__":
    main()
