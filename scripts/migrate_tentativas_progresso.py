#!/usr/bin/env python3
"""Migração: adiciona campos de progresso/controle à collection `tentativas`.

Campos adicionados se não existirem:
  - questoes_respondidas (number) — progresso em tempo real; sem este campo o
    portal exibe sempre "0 de N respondidas" porque o PATCH é ignorado pelo PB
  - numero_tentativa     (number) — número sequencial da tentativa por aluno;
    usado para ordenar o histórico e exibir "Tentativa 1, 2, 3..."
  - nota_final           (number) — nota calculada em pontos (opcional, override
    da nota automática); usado pelo boletim e pela tela de notas do professor

Idempotente: pode ser executado múltiplas vezes sem efeitos colaterais.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_tentativas_progresso.py
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")

CAMPOS_NOVOS = [
    {"name": "questoes_respondidas", "type": "number", "required": False,
     "options": {"min": None, "max": None}},
    {"name": "numero_tentativa", "type": "number", "required": False,
     "options": {"min": None, "max": None}},
    {"name": "nota_final", "type": "number", "required": False,
     "options": {"min": None, "max": None}},
]


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
    existentes = {f["name"] for f in schema}

    adicionados = []
    for campo in CAMPOS_NOVOS:
        if campo["name"] not in existentes:
            schema.append(campo)
            adicionados.append(campo["name"])
            print(f"  + {campo['name']} ({campo['type']})")

    if not adicionados:
        print("[OK] Todos os campos já existem — nada a fazer.")
        return

    resp = requests.patch(
        f"{PB_URL}/api/collections/tentativas",
        headers=_headers(token),
        json={"schema": schema},
    )
    if not resp.ok:
        print(f"[ERRO] {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] {len(adicionados)} campo(s) adicionado(s) à collection 'tentativas': "
          f"{', '.join(adicionados)}")


if __name__ == "__main__":
    main()
