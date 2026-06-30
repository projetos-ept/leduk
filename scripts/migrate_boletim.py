#!/usr/bin/env python3
"""Migração: cria as collections do Boletim (boletins, unidades, recuperacao_final).

Idempotente — pula collections que já existem. Resolve os IDs das collections
referenciadas (turmas, disciplinas, atividades, boletins) em runtime.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_boletim.py
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
    resp = requests.post(
        f"{PB_URL}/api/admins/auth-with-password",
        json={"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["token"]


def get_collection(token: str, name: str) -> dict | None:
    resp = requests.get(f"{PB_URL}/api/collections/{name}", headers=_headers(token))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def col_id(token: str, name: str) -> str:
    col = get_collection(token, name)
    if not col:
        print(f"[ERRO] collection '{name}' não encontrada.", file=sys.stderr)
        sys.exit(1)
    return col["id"]


def criar_collection(token: str, payload: dict) -> None:
    nome = payload["name"]
    if get_collection(token, nome):
        print(f"[OK] Collection '{nome}' já existe.")
        return
    payload.setdefault("type", "base")
    payload.setdefault("listRule", "")
    payload.setdefault("viewRule", "")
    payload.setdefault("createRule", AUTH_RULE)
    payload.setdefault("updateRule", AUTH_RULE)
    payload.setdefault("deleteRule", AUTH_RULE)
    resp = requests.post(f"{PB_URL}/api/collections", headers=_headers(token), json=payload)
    resp.raise_for_status()
    print(f"[OK] Collection '{nome}' criada.")


def _rel(collection_id: str, required: bool, max_select: int = 1) -> dict:
    return {"collectionId": collection_id, "maxSelect": max_select, "cascadeDelete": False}


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    turmas_id = col_id(token, "turmas")
    disc_id = col_id(token, "disciplinas")
    ativ_id = col_id(token, "atividades")

    # 1. boletins
    criar_collection(token, {
        "name": "boletins",
        "schema": [
            {"name": "turma", "type": "relation", "required": True, "options": _rel(turmas_id, True)},
            {"name": "media_aprovacao", "type": "number", "required": False},
            {"name": "ativo", "type": "bool", "required": False},
            {"name": "liberado", "type": "bool", "required": False},
            {"name": "ano", "type": "number", "required": False},
        ],
    })
    boletins_id = col_id(token, "boletins")

    # 2. unidades
    criar_collection(token, {
        "name": "unidades",
        "schema": [
            {"name": "boletim", "type": "relation", "required": True, "options": _rel(boletins_id, True)},
            {"name": "disciplina", "type": "relation", "required": True, "options": _rel(disc_id, True)},
            {"name": "numero", "type": "number", "required": True},
            {"name": "titulo", "type": "text", "required": False},
            {"name": "atividades", "type": "relation", "required": False, "options": _rel(ativ_id, False, 999)},
            {"name": "rec_atividade", "type": "relation", "required": False, "options": _rel(ativ_id, False)},
            {"name": "rec_nota_manual", "type": "number", "required": False},
        ],
    })

    # 3. recuperacao_final
    criar_collection(token, {
        "name": "recuperacao_final",
        "schema": [
            {"name": "boletim", "type": "relation", "required": True, "options": _rel(boletins_id, True)},
            {"name": "disciplina", "type": "relation", "required": True, "options": _rel(disc_id, True)},
            {"name": "rec_atividade", "type": "relation", "required": False, "options": _rel(ativ_id, False)},
            {"name": "rec_nota_manual", "type": "number", "required": False},
        ],
    })

    print("Migração do boletim concluída.")


if __name__ == "__main__":
    main()
