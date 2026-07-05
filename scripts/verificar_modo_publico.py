#!/usr/bin/env python3
"""Verificação profunda do modo público de atividades no PocketBase.

O fluxo público roda SEM token (visitante anônimo), então além dos campos
novos, as regras da collection `tentativas` precisam permitir operações
anônimas:

  - createRule: ""  (criar tentativa/respostas sem login)
  - updateRule: ""  (atualizar progresso e concluir tentativa sem login)
  - listRule:   ""  (contar tentativas por email no formulário público)
  - viewRule:   ""

Checagens executadas:
  1. Campos em `turmas`: publica, descricao
  2. Campos em `tentativas`: aluno_email, aluno_turma, questoes_respondidas,
     numero_tentativa, nota_final, tentativa_id
  3. Campo `aluno_id` opcional em `tentativas`
  4. Regras de `tentativas` (create/update/list/view abertas)
  5. Teste real: POST anônimo em tentativas + registro de resposta com
     tentativa_id + GET com filter=tentativa_id="..." (cria e apaga os
     registros de teste) — reproduz exatamente o que quebrou em produção
     quando tentativa_id não existia no schema (400 "invalid filter")

Modo somente-leitura por padrão. Com --fix (ou FIX=1), adiciona os campos
ausentes e abre as regras necessárias.

Uso:
  PB_URL=https://... PB_ADMIN_EMAIL=... PB_ADMIN_PASSWORD=... \\
    python scripts/verificar_modo_publico.py [--fix]
"""
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")
FIX = "--fix" in sys.argv or os.environ.get("FIX") == "1"

CAMPOS_TURMAS = [
    {"name": "publica", "type": "bool", "required": False},
    {"name": "descricao", "type": "text", "required": False},
]
CAMPOS_TENTATIVAS = [
    {"name": "aluno_email", "type": "text", "required": False},
    {"name": "aluno_turma", "type": "text", "required": False},
    {"name": "questoes_respondidas", "type": "number", "required": False,
     "options": {"min": None, "max": None}},
    {"name": "numero_tentativa", "type": "number", "required": False,
     "options": {"min": None, "max": None}},
    {"name": "nota_final", "type": "number", "required": False,
     "options": {"min": None, "max": None}},
    {"name": "tentativa_id", "type": "text", "required": False},
]
REGRAS_ABERTAS = ("listRule", "viewRule", "createRule", "updateRule")

problemas: list[str] = []


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


def checar_campos(token: str, col_nome: str, esperados: list) -> None:
    col = get_collection(token, col_nome)
    if not col:
        problemas.append(f"collection '{col_nome}' NÃO EXISTE")
        print(f"[FALHA] Collection '{col_nome}' não encontrada!")
        return
    schema = col.get("schema", [])
    existentes = {f["name"] for f in schema}
    faltando = [c for c in esperados if c["name"] not in existentes]
    if not faltando:
        print(f"[OK] '{col_nome}': todos os campos presentes "
              f"({', '.join(c['name'] for c in esperados)})")
        return
    nomes = ", ".join(c["name"] for c in faltando)
    if FIX:
        schema.extend(faltando)
        r = requests.patch(f"{PB_URL}/api/collections/{col_nome}",
                           headers=_headers(token), json={"schema": schema})
        if r.ok:
            print(f"[CORRIGIDO] '{col_nome}': campos adicionados → {nomes}")
        else:
            problemas.append(f"falha ao corrigir campos de {col_nome}: {r.text[:200]}")
            print(f"[FALHA] '{col_nome}': não foi possível adicionar campos: {r.text[:200]}")
    else:
        problemas.append(f"'{col_nome}' sem campos: {nomes}")
        print(f"[FALHA] '{col_nome}': campos AUSENTES → {nomes}")


def checar_aluno_id_opcional(token: str) -> None:
    """aluno_id="" é como o modo público identifica um respondente sem conta.
    Se o campo for required, o PocketBase recusa toda tentativa pública."""
    col = get_collection(token, "tentativas")
    if not col:
        return  # já reportado por checar_campos
    schema = col.get("schema", [])
    campo = next((f for f in schema if f.get("name") == "aluno_id"), None)
    if not campo:
        problemas.append("campo 'aluno_id' não encontrado em 'tentativas'")
        print("[FALHA] 'tentativas': campo 'aluno_id' não encontrado.")
        return
    if not campo.get("required", False):
        print("[OK] 'tentativas.aluno_id': já é opcional (aceita respondente público).")
        return
    if FIX:
        campo["required"] = False
        r = requests.patch(f"{PB_URL}/api/collections/tentativas",
                           headers=_headers(token), json={"schema": schema})
        if r.ok:
            print("[CORRIGIDO] 'tentativas.aluno_id': agora é opcional.")
        else:
            problemas.append(f"falha ao tornar aluno_id opcional: {r.text[:200]}")
            print(f"[FALHA] não foi possível corrigir aluno_id: {r.text[:200]}")
    else:
        problemas.append("'tentativas.aluno_id' é required=True — bloqueia o modo público")
        print("[FALHA] 'tentativas.aluno_id' é required=True — todo POST anônimo "
              "(aluno_id=\"\") é rejeitado pelo PocketBase.")


def checar_regras_tentativas(token: str) -> None:
    col = get_collection(token, "tentativas")
    if not col:
        problemas.append("collection 'tentativas' NÃO EXISTE")
        print("[FALHA] Collection 'tentativas' não encontrada!")
        return
    fechadas = {r: col.get(r) for r in REGRAS_ABERTAS if col.get(r) not in ("",)}
    if not fechadas:
        print("[OK] 'tentativas': regras abertas para o fluxo anônimo.")
        return
    detalhe = ", ".join(f"{k}={v!r}" for k, v in fechadas.items())
    if FIX:
        r = requests.patch(f"{PB_URL}/api/collections/tentativas",
                           headers=_headers(token),
                           json={k: "" for k in fechadas})
        if r.ok:
            print(f"[CORRIGIDO] 'tentativas': regras abertas ({', '.join(fechadas)})")
        else:
            problemas.append(f"falha ao abrir regras: {r.text[:200]}")
            print(f"[FALHA] não foi possível abrir regras: {r.text[:200]}")
    else:
        problemas.append(f"regras de 'tentativas' bloqueiam anônimos: {detalhe}")
        print(f"[FALHA] 'tentativas': regras bloqueiam o fluxo anônimo → {detalhe}")
        print("        (é esta a causa de 'rota pública não gera registro')")


def teste_real_criacao_anonima(token_admin: str) -> None:
    """POST sem Authorization — exatamente o que o visitante público faz."""
    payload = {"aluno_id": "", "aluno_nome": "__teste_modo_publico__",
               "concluida": False, "nota_liberada": False}
    r = requests.post(f"{PB_URL}/api/collections/tentativas/records", json=payload)
    if not r.ok:
        problemas.append(f"POST anônimo falhou: {r.status_code} {r.text[:200]}")
        print(f"[FALHA] Teste real: POST anônimo recusado — {r.status_code}")
        print(f"        Resposta do PocketBase: {r.text[:300]}")
        return

    rec_id = r.json().get("id", "")
    print("[OK] Teste real: criação anônima de tentativa funcionou.")

    # PATCH anônimo (progresso/conclusão usam updateRule)
    p = requests.patch(f"{PB_URL}/api/collections/tentativas/records/{rec_id}",
                       json={"questoes_respondidas": 1})
    if p.ok:
        print("[OK] Teste real: atualização anônima (progresso) funcionou.")
    else:
        problemas.append(f"PATCH anônimo falhou: {p.status_code} {p.text[:200]}")
        print(f"[FALHA] PATCH anônimo: {p.status_code} — {p.text[:200]}")

    # Registro de resposta (o que /htmx/responder grava) + filtro por tentativa_id
    # (exatamente o que listar_respostas_tentativa faz — sintoma real já visto em
    # produção: 400 "invalid filter" quando o campo não existe no schema)
    resp_payload = {"atividade": "", "questao": "", "tipo_questao": "mc4",
                    "resposta_dada": "A", "correta": True, "score_raw": 1,
                    "score_max": 1, "tentativa_id": rec_id}
    rp = requests.post(f"{PB_URL}/api/collections/tentativas/records", json=resp_payload)
    if rp.ok:
        resp_id = rp.json().get("id", "")
        g = requests.get(f"{PB_URL}/api/collections/tentativas/records",
                         params={"filter": f'tentativa_id="{rec_id}"'})
        if g.ok:
            print("[OK] Teste real: filtro por tentativa_id funcionou (revisão/comprovante ok).")
        else:
            problemas.append(f"filtro tentativa_id falhou: {g.status_code} {g.text[:200]}")
            print(f"[FALHA] GET com filter=tentativa_id: {g.status_code} — {g.text[:300]}")
            print("        (é esta a causa de revisão/comprovante não mostrar respostas)")
        requests.delete(f"{PB_URL}/api/collections/tentativas/records/{resp_id}",
                        headers=_headers(token_admin))
    else:
        problemas.append(f"POST de resposta falhou: {rp.status_code} {rp.text[:200]}")
        print(f"[FALHA] POST de registro de resposta: {rp.status_code} — {rp.text[:300]}")

    requests.delete(f"{PB_URL}/api/collections/tentativas/records/{rec_id}",
                    headers=_headers(token_admin))
    print("     (registros de teste removidos)")


def main() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando em {PB_URL} ... (modo {'FIX' if FIX else 'somente leitura'})")
    token = autenticar_admin()
    print("[OK] Admin autenticado.\n")

    print("── 1/5 Campos de 'turmas' ──")
    checar_campos(token, "turmas", CAMPOS_TURMAS)
    print("\n── 2/5 Campos de 'tentativas' ──")
    checar_campos(token, "tentativas", CAMPOS_TENTATIVAS)
    print("\n── 3/5 Campo 'tentativas.aluno_id' opcional ──")
    checar_aluno_id_opcional(token)
    print("\n── 4/5 Regras de 'tentativas' ──")
    checar_regras_tentativas(token)
    print("\n── 5/5 Teste real de criação anônima + filtro tentativa_id ──")
    teste_real_criacao_anonima(token)

    print()
    if problemas:
        print(f"RESULTADO: {len(problemas)} problema(s) encontrado(s):")
        for p in problemas:
            print(f"  ✗ {p}")
        if not FIX:
            print("\nExecute novamente com --fix para corrigir automaticamente.")
        sys.exit(2)
    print("RESULTADO: modo público 100% funcional. ✓")


if __name__ == "__main__":
    main()
