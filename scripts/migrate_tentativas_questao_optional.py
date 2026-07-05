#!/usr/bin/env python3
"""Migração: torna `questao` e `aluno_id` opcionais na collection `tentativas`.

- `questao`: quando uma questão é excluída, o campo das tentativas vinculadas
  é anulado (set to null) para preservar o histórico do aluno — exige
  required: false.
- `aluno_id`: o modo público (atividades respondidas por visitantes sem
  conta) grava tentativas com aluno_id="" e identifica o respondente por
  aluno_email/aluno_turma. Se aluno_id for required, o PocketBase rejeita
  toda tentativa pública com validation_required, mesmo enviando "" — nada
  é gravado, e o formulário público falha silenciosamente para quem responde.

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
    campos_alvo = ("questao", "aluno_id")
    alterados = []

    for nome_campo in campos_alvo:
        campo = next((f for f in schema if f.get("name") == nome_campo), None)
        if not campo:
            print(f"[AVISO] Campo '{nome_campo}' não encontrado na collection 'tentativas'.")
            continue
        if not campo.get("required", False):
            print(f"[OK] Campo '{nome_campo}' já é opcional — nada a fazer.")
            continue
        print(f"  Campo '{nome_campo}': required={campo['required']}  →  required=false")
        campo["required"] = False
        alterados.append(nome_campo)

    if not alterados:
        print("[OK] Nenhuma alteração necessária.")
        return

    resp = requests.patch(
        f"{PB_URL}/api/collections/tentativas",
        headers=_headers(token),
        json={"schema": schema},
    )
    resp.raise_for_status()
    print(f"[OK] Campo(s) {', '.join(alterados)} agora são opcionais.")
    if "questao" in alterados:
        print("     Exclusão de questões com tentativas vinculadas funciona.")
    if "aluno_id" in alterados:
        print("     Modo público (respondentes sem conta) agora grava tentativas corretamente.")


if __name__ == "__main__":
    main()
