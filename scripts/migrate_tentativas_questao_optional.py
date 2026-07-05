#!/usr/bin/env python3
"""Migração: corrige o schema de `tentativas` para o que o código já assume.

- `tentativa_id` (text, NOVO CAMPO): liga cada registro de resposta
  (criado em /htmx/responder) ao registro-pai da tentativa. Esse campo
  nunca foi adicionado ao schema por nenhuma migração — o PocketBase
  silenciosamente ignora campos não declarados em POST/PATCH, então toda
  resposta gravada em produção perdia esse vínculo. O sintoma só aparece
  na LEITURA: `GET .../tentativas/records?filter=tentativa_id="..."`
  retorna 400 Bad Request ("invalid filter") porque o campo não existe
  de fato no schema — não porque a query esteja errada. Isso quebra
  silenciosamente qualquer tela de revisão/gabarito/comprovante que
  dependa de listar as respostas de uma tentativa específica.
- `questao` (opcional): quando uma questão é excluída, o campo das
  tentativas vinculadas é anulado (set to null) para preservar o
  histórico do aluno — exige required: false.
- `aluno_id` (opcional): o modo público (atividades respondidas por
  visitantes sem conta) grava tentativas com aluno_id="" e identifica o
  respondente por aluno_email/aluno_turma. Se aluno_id for required, o
  PocketBase rejeita toda tentativa pública com validation_required,
  mesmo enviando "" — nada é gravado, e o formulário público falha
  silenciosamente para quem responde.

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
    alterados = []

    # 1. tentativa_id: campo NOVO, precisa ser criado se ausente
    if not any(f.get("name") == "tentativa_id" for f in schema):
        schema.append({"name": "tentativa_id", "type": "text", "required": False})
        alterados.append("tentativa_id (novo campo)")
        print("  + tentativa_id (text, required=false) — campo criado")
    else:
        print("[OK] Campo 'tentativa_id' já existe — nada a fazer.")

    # 2. questao / aluno_id: campos existentes que precisam virar opcionais
    for nome_campo in ("questao", "aluno_id"):
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
    print(f"[OK] Campo(s) alterado(s): {', '.join(alterados)}.")
    if any("tentativa_id" in a for a in alterados):
        print("     Revisão/gabarito/comprovante agora conseguem listar as respostas de uma tentativa.")
    if "questao" in alterados:
        print("     Exclusão de questões com tentativas vinculadas funciona.")
    if "aluno_id" in alterados:
        print("     Modo público (respondentes sem conta) agora grava tentativas corretamente.")


if __name__ == "__main__":
    main()
