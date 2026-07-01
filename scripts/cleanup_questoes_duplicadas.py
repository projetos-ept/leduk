#!/usr/bin/env python3
"""Localiza e (opcionalmente) remove questões duplicadas/órfãs do banco.

Contexto: uma falha na importação por JSON podia deixar para trás uma questão
"órfã" — o registro pai criado com o enunciado, mas sem alternativas/itens,
porque a criação de um subitem falhava depois da questão já ter sido gravada
(sem rollback). Reimportar o mesmo arquivo então criava cópias. Este script
varre o banco em busca de questões com o mesmo (disciplina, tipo, enunciado
normalizado) e ajuda a decidir qual manter e qual remover.

Critério de escolha do "keeper" (mantido) em cada grupo de duplicatas:
  1. mais subitens (alternativas/itens_vf/pares_associativos) — mais completa
  2. em empate, o registro mais antigo (created)

Por padrão roda em modo DRY-RUN (só relata). Use --apply para de fato remover:
  - remove o ID de atividades.questoes[] que referenciam a questão removida
  - apaga os subitens da questão removida (alternativas/itens_vf/pares)
  - apaga o registro da questão

Uso:
  PB_URL=http://127.0.0.1:8090 \\
  PB_ADMIN_EMAIL=admin@example.com \\
  PB_ADMIN_PASSWORD=senha \\
    python scripts/cleanup_questoes_duplicadas.py            # dry-run
    python scripts/cleanup_questoes_duplicadas.py --apply     # remove de fato
    python scripts/cleanup_questoes_duplicadas.py --disciplina <id> --apply
"""
import argparse
import os
import sys

import requests

PB_URL = os.environ.get("PB_URL", "http://127.0.0.1:8090").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "")

SUBITEM_COLLECTION = {
    "mc4": "alternativas", "mc5": "alternativas",
    "vf": "itens_vf", "associativa": "pares_associativos",
    "aberta": None,
}


def _headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


def autenticar_admin() -> str:
    resp = requests.post(f"{PB_URL}/api/admins/auth-with-password",
                         json={"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    resp.raise_for_status()
    return resp.json()["token"]


def _get_paginado(token: str, collection: str, filtro: str | None = None) -> list:
    itens = []
    pagina = 1
    while True:
        params = {"page": pagina, "perPage": 200}
        if filtro:
            params["filter"] = filtro
        r = requests.get(f"{PB_URL}/api/collections/{collection}/records",
                         headers=_headers(token), params=params)
        r.raise_for_status()
        data = r.json()
        itens.extend(data.get("items", []))
        if pagina * 200 >= data.get("totalItems", 0):
            break
        pagina += 1
    return itens


def _chave(q: dict) -> tuple:
    enun = " ".join((q.get("enunciado") or "").strip().lower().split())
    return (q.get("disciplina", ""), q.get("tipo", ""), enun)


def _contar_subitens(token: str, questao: dict) -> int:
    col = SUBITEM_COLLECTION.get(questao.get("tipo"))
    if not col:
        return 0
    r = requests.get(f"{PB_URL}/api/collections/{col}/records",
                     headers=_headers(token),
                     params={"filter": f'questao="{questao["id"]}"', "perPage": 1})
    r.raise_for_status()
    return r.json().get("totalItems", 0)


def _remover_de_atividades(token: str, questao_id: str) -> int:
    ativs = _get_paginado(token, "atividades", filtro=f'questoes~"{questao_id}"')
    removidas = 0
    for a in ativs:
        questoes = [q for q in (a.get("questoes") or []) if q != questao_id]
        r = requests.patch(f"{PB_URL}/api/collections/atividades/records/{a['id']}",
                           headers=_headers(token), json={"questoes": questoes})
        if r.ok:
            removidas += 1
    return removidas


def _apagar_subitens(token: str, questao: dict) -> None:
    col = SUBITEM_COLLECTION.get(questao.get("tipo"))
    if not col:
        return
    itens = _get_paginado(token, col, filtro=f'questao="{questao["id"]}"')
    for it in itens:
        requests.delete(f"{PB_URL}/api/collections/{col}/records/{it['id']}",
                        headers=_headers(token))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="remove de fato (padrão: dry-run)")
    ap.add_argument("--disciplina", default="", help="limitar a uma disciplina específica")
    args = ap.parse_args()

    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Erro: defina PB_ADMIN_EMAIL e PB_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando em {PB_URL} ...")
    token = autenticar_admin()
    print("[OK] Admin autenticado.")

    filtro = f'disciplina="{args.disciplina}"' if args.disciplina else None
    questoes = _get_paginado(token, "questoes", filtro=filtro)
    print(f"[OK] {len(questoes)} questão(ões) carregada(s).")

    grupos: dict[tuple, list] = {}
    for q in questoes:
        grupos.setdefault(_chave(q), []).append(q)

    duplicados = {k: v for k, v in grupos.items() if len(v) > 1}
    if not duplicados:
        print("Nenhuma questão duplicada encontrada. Nada a fazer.")
        return

    total_remover = 0
    for (disc, tipo, enun), grupo in duplicados.items():
        for q in grupo:
            q["_subitens"] = _contar_subitens(token, q)
        grupo.sort(key=lambda q: (-q["_subitens"], q.get("created", "")))
        keeper, *resto = grupo
        print(f"\nGrupo duplicado — disciplina={disc} tipo={tipo} enunciado={enun[:60]!r}")
        print(f"  MANTÉM  {keeper['id']} ({keeper['_subitens']} subitens, created={keeper.get('created')})")
        for q in resto:
            print(f"  REMOVE  {q['id']} ({q['_subitens']} subitens, created={q.get('created')})")
            total_remover += 1
            if args.apply:
                n = _remover_de_atividades(token, q["id"])
                _apagar_subitens(token, q)
                requests.delete(f"{PB_URL}/api/collections/questoes/records/{q['id']}",
                                headers=_headers(token))
                print(f"          → removida ({n} atividade(s) desvinculada(s))")

    if args.apply:
        print(f"\n[OK] {total_remover} questão(ões) duplicada(s) removida(s).")
    else:
        print(f"\n[DRY-RUN] {total_remover} questão(ões) seriam removidas. "
              f"Rode novamente com --apply para aplicar.")


if __name__ == "__main__":
    main()
