#!/usr/bin/env python3
"""Migração: corrige viewRule da collection `users` para professores/admins.

Sem esta regra, a query `expand=aluno` em `matriculas` retorna vazia porque
o PocketBase recusa o expand quando o token não tem permissão de leitura na
collection de destino (users). O resultado é o ID bruto do aluno sendo
exibido em vez do nome/email.

A regra aplicada permite leitura para qualquer usuário autenticado:
  viewRule: @request.auth.id != ""

Idempotente: pode ser executado múltiplas vezes sem efeitos colaterais.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_users_viewrule.py
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

    col = get_collection(token, "users")
    if not col:
        print("[ERRO] Collection 'users' não encontrada.", file=sys.stderr)
        sys.exit(1)

    view_rule = col.get("viewRule")
    if view_rule == AUTH_RULE:
        print("[OK] viewRule já está correta — nada a fazer.")
        return

    print(f"  viewRule atual: {view_rule!r}  →  {AUTH_RULE!r}")

    resp = requests.patch(
        f"{PB_URL}/api/collections/users",
        headers=_headers(token),
        json={"viewRule": AUTH_RULE},
    )
    resp.raise_for_status()
    print("[OK] viewRule atualizada. Expand de aluno em matrículas agora funciona.")


if __name__ == "__main__":
    main()
