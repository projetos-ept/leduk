#!/usr/bin/env python3
"""Migração: torna o campo `questao` da collection `tentativas` opcional.

Quando uma questão é excluída, o campo `questao` das tentativas vinculadas é
anulado (set to null) para preservar o histórico do aluno. Isso requer que o
campo `questao` não seja obrigatório (required: false).

Idempotente: pode ser executado múltiplas vezes sem efeitos colaterais.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_tentativas_questao_optional.py
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


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    col = get_collection(token, "tentativas")
    if not col:
        print("[ERRO] Collection 'tentativas' não encontrada.", file=sys.stderr)
        sys.exit(1)

    schema = col.get("schema", [])
    questao_field = next((f for f in schema if f.get("name") == "questao"), None)

    if not questao_field:
        print("[AVISO] Campo 'questao' não encontrado na collection 'tentativas'.")
        return

    if not questao_field.get("required", False):
        print("[OK] Campo 'questao' já é opcional — nada a fazer.")
        return

    print(f"  Campo 'questao': required={questao_field['required']}  →  required=false")

    questao_field["required"] = False
    updated_schema = [f if f.get("name") != "questao" else questao_field for f in schema]

    resp = requests.patch(
        f"{PB_URL}/api/collections/tentativas",
        headers=_headers(token),
        json={"schema": updated_schema},
    )
    resp.raise_for_status()
    print("[OK] Campo 'questao' agora é opcional. Exclusão de questões com tentativas vinculadas funciona.")


if __name__ == "__main__":
    main()
