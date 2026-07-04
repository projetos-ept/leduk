#!/usr/bin/env python3
"""Migração: adiciona campos ausentes à collection `atividades`.

Campos adicionados se não existirem:
  - max_tentativas  (number)  — limite de tentativas por aluno; 0 = ilimitado
  - tempo_limite    (number)  — tempo em minutos; 0 = sem limite
  - valor_total     (number)  — pontuação total da atividade
  - disponivel_de   (date)    — data/hora de abertura
  - disponivel_ate  (date)    — data/hora de encerramento
  - nota_automatica (bool)    — corrigir automaticamente ao concluir
  - exibir_feedback_pos (bool) — mostrar gabarito após conclusão
  - embaralhar      (bool)    — embaralhar ordem das questões
  - modo_prova      (bool)    — ocultar feedback durante e gabarito após
  - multidisciplinar (bool)   — atividade aparece na aba multidisciplinar
  - ativa           (bool)    — controla visibilidade para alunos

Idempotente: pode ser executado múltiplas vezes sem efeitos colaterais.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_atividades_campos.py
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")

CAMPOS_NOVOS = [
    {"name": "max_tentativas", "type": "number", "required": False,
     "options": {"min": None, "max": None}},
    {"name": "tempo_limite", "type": "number", "required": False,
     "options": {"min": None, "max": None}},
    {"name": "valor_total", "type": "number", "required": False,
     "options": {"min": None, "max": None}},
    {"name": "disponivel_de", "type": "date", "required": False,
     "options": {"min": "", "max": ""}},
    {"name": "disponivel_ate", "type": "date", "required": False,
     "options": {"min": "", "max": ""}},
    {"name": "nota_automatica", "type": "bool", "required": False},
    {"name": "exibir_feedback_pos", "type": "bool", "required": False},
    {"name": "embaralhar", "type": "bool", "required": False},
    {"name": "modo_prova", "type": "bool", "required": False},
    {"name": "multidisciplinar", "type": "bool", "required": False},
    {"name": "ativa", "type": "bool", "required": False},
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

    col = get_collection(token, "atividades")
    if not col:
        print("[ERRO] Collection 'atividades' não encontrada.", file=sys.stderr)
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
        f"{PB_URL}/api/collections/atividades",
        headers=_headers(token),
        json={"schema": schema},
    )
    if not resp.ok:
        print(f"[ERRO] {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] {len(adicionados)} campo(s) adicionado(s) à collection 'atividades': "
          f"{', '.join(adicionados)}")


if __name__ == "__main__":
    main()
