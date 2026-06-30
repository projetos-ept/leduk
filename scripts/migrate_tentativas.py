#!/usr/bin/env python3
"""Migração: adiciona campo 'atividade' (relation) à collection tentativas
e preenche registros antigos copiando o valor do campo legado 'disciplina'.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_tentativas.py

A variável PB_ATIVIDADES_COLLECTION_ID deve ser o ID da collection atividades
(visível em /api/collections). Já está pré-configurada com o valor da instância
de produção, mas pode ser sobrescrita por variável de ambiente.
"""
import json
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")
ATIVIDADES_COL_ID = os.environ.get("PB_ATIVIDADES_COLLECTION_ID", "44qehlo0jku49lq")

CAMPO_ATIVIDADE = {
    "name": "atividade",
    "type": "relation",
    "required": False,
    "options": {
        "collectionId": ATIVIDADES_COL_ID,
        "maxSelect": 1,
        "cascadeDelete": False,
    },
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
    if any(f["name"] == "atividade" for f in schema):
        print("[OK] Campo 'atividade' já existe no schema — nada a fazer.")
        return

    schema.append(CAMPO_ATIVIDADE)
    resp = requests.patch(
        f"{PB_URL}/api/collections/{collection['id']}",
        headers=_headers(token),
        json={"schema": schema},
    )
    resp.raise_for_status()
    print("[OK] Campo 'atividade' adicionado ao schema de tentativas.")


def migrar_registros(token: str) -> int:
    """Copia disciplina → atividade para registros legados.

    Registros criados antes da renomeação têm o ID da atividade em 'disciplina'.
    Registros novos (após o fix) já têm 'atividade' preenchido.
    """
    migrados = 0
    pagina = 1
    per_page = 200

    while True:
        resp = requests.get(
            f"{PB_URL}/api/collections/tentativas/records",
            headers=_headers(token),
            params={"page": pagina, "perPage": per_page, "sort": "created"},
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            if item.get("atividade"):
                continue
            old_id = item.get("disciplina", "").strip()
            if not old_id:
                continue
            patch = requests.patch(
                f"{PB_URL}/api/collections/tentativas/records/{item['id']}",
                headers=_headers(token),
                json={"atividade": old_id},
            )
            if patch.ok:
                migrados += 1
            else:
                print(f"  [WARN] {item['id']}: {patch.status_code} {patch.text[:120]}")

        total = data.get("totalItems", 0)
        if pagina * per_page >= total:
            break
        pagina += 1

    return migrados


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print(
            "Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    collection = get_collection(token, "tentativas")
    adicionar_campo_schema(token, collection)

    n = migrar_registros(token)
    print(f"[OK] {n} registro(s) migrado(s) (disciplina → atividade).")
    print("Migração concluída.")


if __name__ == "__main__":
    main()
