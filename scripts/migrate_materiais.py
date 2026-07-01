#!/usr/bin/env python3
"""Migração do modelo de materiais para banco reutilizável por disciplina.

Espelha o modelo de questões/atividades: o material pertence ao banco da
disciplina (ganha o campo `assunto`) e a turma passa a "usar" materiais através
da collection pivô `turma_materiais` — o mesmo material pode aparecer em várias
turmas sem duplicar o registro.

Passos (todos idempotentes):
  1. Adiciona o campo `assunto` (text) à collection `materiais`.
  2. Cria a collection `turma_materiais` (pivô turma↔material) se não existir.
  3. Backfill: para cada material legado com `turma` preenchido, cria o registro
     correspondente em `turma_materiais` (preservando a exibição atual do portal).

A leitura no portal (`pb.listar_materiais`) é retrocompatível: enquanto não houver
registros em `turma_materiais`, ela cai no filtro legado `materiais.turma`. Assim
o portal nunca quebra, antes ou depois desta migração.

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/migrate_materiais.py
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
    resp = requests.get(f"{PB_URL}/api/collections/{name}", headers=_headers(token))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


# ── Passo 1: campo assunto em materiais ─────────────────────────────────────────

def adicionar_assunto(token: str) -> None:
    col = get_collection(token, "materiais")
    if not col:
        print("[ERRO] collection 'materiais' não encontrada.", file=sys.stderr)
        sys.exit(1)
    schema = col.get("schema", [])
    if any(f["name"] == "assunto" for f in schema):
        print("[OK] Campo 'assunto' já existe em materiais.")
        return
    schema.append({"name": "assunto", "type": "text", "required": False})
    resp = requests.patch(
        f"{PB_URL}/api/collections/{col['id']}",
        headers=_headers(token), json={"schema": schema},
    )
    resp.raise_for_status()
    print("[OK] Campo 'assunto' adicionado a materiais.")


# ── Passo 2: collection turma_materiais ─────────────────────────────────────────

def criar_turma_materiais(token: str) -> None:
    if get_collection(token, "turma_materiais"):
        print("[OK] Collection 'turma_materiais' já existe.")
        return

    turmas = get_collection(token, "turmas")
    materiais = get_collection(token, "materiais")
    if not turmas or not materiais:
        print("[ERRO] collections 'turmas'/'materiais' não encontradas.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "name": "turma_materiais",
        "type": "base",
        "listRule": "",
        "viewRule": "",
        "createRule": '@request.auth.id != ""',
        "updateRule": '@request.auth.id != ""',
        "deleteRule": '@request.auth.id != ""',
        "schema": [
            {"name": "turma", "type": "relation", "required": True,
             "options": {"collectionId": turmas["id"], "maxSelect": 1, "cascadeDelete": True}},
            {"name": "material", "type": "relation", "required": True,
             "options": {"collectionId": materiais["id"], "maxSelect": 1, "cascadeDelete": True}},
            {"name": "ordem", "type": "number", "required": False},
            {"name": "ativo", "type": "bool", "required": False},
        ],
    }
    resp = requests.post(f"{PB_URL}/api/collections", headers=_headers(token), json=payload)
    resp.raise_for_status()
    print("[OK] Collection 'turma_materiais' criada.")


# ── Passo 3: backfill ───────────────────────────────────────────────────────────

def _pivo_existe(token: str, turma_id: str, material_id: str) -> bool:
    resp = requests.get(
        f"{PB_URL}/api/collections/turma_materiais/records",
        headers=_headers(token),
        params={"filter": f'turma="{turma_id}"&&material="{material_id}"', "perPage": 1},
    )
    resp.raise_for_status()
    return resp.json().get("totalItems", 0) > 0


def backfill(token: str) -> int:
    criados = 0
    pagina = 1
    while True:
        resp = requests.get(
            f"{PB_URL}/api/collections/materiais/records",
            headers=_headers(token),
            params={"page": pagina, "perPage": 200, "sort": "ordem"},
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            break
        for m in items:
            turma_id = (m.get("turma") or "").strip()
            if not turma_id:
                continue
            if _pivo_existe(token, turma_id, m["id"]):
                continue
            novo = requests.post(
                f"{PB_URL}/api/collections/turma_materiais/records",
                headers=_headers(token),
                json={
                    "turma": turma_id,
                    "material": m["id"],
                    "ordem": m.get("ordem", 0) or 0,
                    "ativo": m.get("ativo", True),
                },
            )
            if novo.ok:
                criados += 1
            else:
                print(f"  [WARN] material {m['id']}: {novo.status_code} {novo.text[:120]}")
        if pagina * 200 >= data.get("totalItems", 0):
            break
        pagina += 1
    return criados


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    adicionar_assunto(token)
    criar_turma_materiais(token)
    n = backfill(token)
    print(f"[OK] {n} vínculo(s) turma_materiais criado(s) no backfill.")
    print("Migração de materiais concluída.")


if __name__ == "__main__":
    main()
