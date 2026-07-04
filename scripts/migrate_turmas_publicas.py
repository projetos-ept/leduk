#!/usr/bin/env python3
"""Migração: modo público de atividades (turmas públicas sem matrícula).

Campos adicionados se não existirem:

  turmas:
    - publica    (bool) — turma visível via rotas /publica/* sem login
    - descricao  (text) — texto de apresentação da turma pública

  tentativas:
    - aluno_email (text) — email do respondente público (controle de tentativas)
    - aluno_turma (text) — turma livre digitada pelo respondente público

Tentativas públicas são gravadas com aluno_id="" e identificadas pelo email.
Boletins não são afetados: turmas públicas nunca têm boletim.ativo=true por
padrão (o padrão atual da collection boletins já é ativo=false).

Idempotente: pode ser executado múltiplas vezes sem efeitos colaterais.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_turmas_publicas.py
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")

CAMPOS = {
    "turmas": [
        {"name": "publica", "type": "bool", "required": False},
        {"name": "descricao", "type": "text", "required": False},
    ],
    "tentativas": [
        {"name": "aluno_email", "type": "text", "required": False},
        {"name": "aluno_turma", "type": "text", "required": False},
    ],
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

    for nome_col, campos in CAMPOS.items():
        col = get_collection(token, nome_col)
        if not col:
            print(f"[ERRO] Collection '{nome_col}' não encontrada.", file=sys.stderr)
            sys.exit(1)

        schema = col.get("schema", [])
        existentes = {f["name"] for f in schema}
        adicionados = []
        for campo in campos:
            if campo["name"] not in existentes:
                schema.append(campo)
                adicionados.append(campo["name"])
                print(f"  + {nome_col}.{campo['name']} ({campo['type']})")

        if not adicionados:
            print(f"[OK] '{nome_col}': todos os campos já existem.")
            continue

        resp = requests.patch(
            f"{PB_URL}/api/collections/{nome_col}",
            headers=_headers(token),
            json={"schema": schema},
        )
        if not resp.ok:
            print(f"[ERRO] {nome_col}: {resp.status_code}: {resp.text}", file=sys.stderr)
            sys.exit(1)
        print(f"[OK] '{nome_col}': {len(adicionados)} campo(s) adicionado(s).")

    print("Migração concluída — modo público de atividades habilitado.")


if __name__ == "__main__":
    main()
