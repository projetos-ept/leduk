#!/usr/bin/env python3
"""Migração: atualiza as regras de acesso da collection `materiais`.

O campo `arquivo` (tipo file) requer que createRule e updateRule permitam
usuários autenticados. Sem essa configuração, uploads multipart retornam 403.

Idempotente: pode ser executado múltiplas vezes sem efeitos colaterais.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_materiais_rules.py
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

    col = get_collection(token, "materiais")
    if not col:
        print("[ERRO] Collection 'materiais' não encontrada.", file=sys.stderr)
        sys.exit(1)

    create_rule = col.get("createRule")
    update_rule = col.get("updateRule")

    if create_rule == AUTH_RULE and update_rule == AUTH_RULE:
        print("[OK] Regras já estão corretas — nada a fazer.")
        return

    print(f"  createRule atual: {create_rule!r}  →  {AUTH_RULE!r}")
    print(f"  updateRule atual: {update_rule!r}  →  {AUTH_RULE!r}")

    resp = requests.patch(
        f"{PB_URL}/api/collections/materiais",
        headers=_headers(token),
        json={"createRule": AUTH_RULE, "updateRule": AUTH_RULE},
    )
    resp.raise_for_status()
    print("[OK] Regras atualizadas. Upload de arquivos para materiais agora funciona.")


if __name__ == "__main__":
    main()
