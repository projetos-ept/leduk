#!/usr/bin/env python3
"""Migração: adiciona "Aberta" às opções válidas de turmas.modalidade.

O campo `modalidade` de `turmas` é um select obrigatório com só 4 valores
(EMI, PROEJA, FIC, EJA) — definidos em setup-leduk-completo.sh. O formulário
de "Nova turma pública" (/professor/publico) usa "Aberta" como valor
sugerido/padrão para turmas sem matrícula, mas esse valor nunca foi
adicionado à lista de opções do select, então o PocketBase rejeitava a
criação com 400 Bad Request.

Idempotente: pode ser executado múltiplas vezes sem efeitos colaterais.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_turma_modalidade_aberta.py
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")

NOVO_VALOR = "Aberta"


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

    col = get_collection(token, "turmas")
    if not col:
        print("[ERRO] Collection 'turmas' não encontrada.", file=sys.stderr)
        sys.exit(1)

    schema = col.get("schema", [])
    campo = next((f for f in schema if f["name"] == "modalidade"), None)
    if not campo:
        print("[ERRO] Campo 'modalidade' não encontrado em 'turmas'.", file=sys.stderr)
        sys.exit(1)

    valores = campo.setdefault("options", {}).setdefault("values", [])
    if NOVO_VALOR in valores:
        print(f"[OK] '{NOVO_VALOR}' já está nas opções de modalidade: {valores}")
        return

    valores.append(NOVO_VALOR)
    resp = requests.patch(
        f"{PB_URL}/api/collections/turmas",
        headers=_headers(token),
        json={"schema": schema},
    )
    if not resp.ok:
        print(f"[ERRO] turmas: {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    print(f"[OK] '{NOVO_VALOR}' adicionada às opções de modalidade: {valores}")
    print("Migração concluída.")


if __name__ == "__main__":
    main()
