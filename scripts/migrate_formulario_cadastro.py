#!/usr/bin/env python3
"""Migração: cria a collection `formularios_cadastro` (link público de cadastro)
e adiciona o campo `matricula` (text) à collection `users`.

Idempotente; resolve o ID de turmas em runtime.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_formulario_cadastro.py
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


def criar_formularios_cadastro(token: str) -> None:
    if get_collection(token, "formularios_cadastro"):
        print("[OK] Collection 'formularios_cadastro' já existe.")
        return
    turmas = get_collection(token, "turmas")
    if not turmas:
        print("[ERRO] collection 'turmas' não encontrada.", file=sys.stderr)
        sys.exit(1)
    payload = {
        "name": "formularios_cadastro",
        "type": "base",
        "listRule": "",
        "viewRule": "",
        "createRule": AUTH_RULE,
        "updateRule": AUTH_RULE,
        "deleteRule": AUTH_RULE,
        "schema": [
            {"name": "turma", "type": "relation", "required": True,
             "options": {"collectionId": turmas["id"], "maxSelect": 1, "cascadeDelete": True}},
            {"name": "token", "type": "text", "required": True},
            {"name": "ativo", "type": "bool", "required": False},
        ],
    }
    r = requests.post(f"{PB_URL}/api/collections", headers=_headers(token), json=payload)
    r.raise_for_status()
    print("[OK] Collection 'formularios_cadastro' criada.")


def adicionar_matricula_users(token: str) -> None:
    users = get_collection(token, "users")
    if not users:
        print("[ERRO] collection 'users' não encontrada.", file=sys.stderr)
        sys.exit(1)
    schema = users.get("schema", [])
    if any(f["name"] == "matricula" for f in schema):
        print("[OK] Campo 'matricula' já existe em users.")
        return
    schema.append({"name": "matricula", "type": "text", "required": False})
    r = requests.patch(f"{PB_URL}/api/collections/{users['id']}",
                       headers=_headers(token), json={"schema": schema})
    r.raise_for_status()
    print("[OK] Campo 'matricula' adicionado a users.")


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)
    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")
    criar_formularios_cadastro(token)
    adicionar_matricula_users(token)
    print("Migração do formulário de cadastro concluída.")


if __name__ == "__main__":
    main()
