"""Cálculo de boletim por turma — funções puras (sem Flask, sem rede).

Modelo de dados de entrada (montado pela camada de rotas/pb):

  tentativas_por_atividade (tpa):
    { atividade_id: {
        "valor_total": float,        # atividades.valor_total
        "tentativas": [ {            # tentativas (registro-pai) do aluno
            "concluida": bool,
            "nota_final": float|None, # pontos já escalados ao valor_total
            "score_raw": int, "score_max": int, "score_percentual": int,
        }, ... ]
    } }

  unidade:  { "numero", "titulo", "disciplina", "atividades": [ids],
              "rec_atividade": id|"", "rec_nota_manual": float|None }

  rec_final: { "disciplina", "rec_atividade": id|"", "rec_nota_manual": float|None }

Regras de pontuação:
  nota_unidade = (soma dos pontos do aluno / soma dos valores_total) × 10
  - usa a MELHOR tentativa de cada atividade
  - atividade não realizada conta como 0 pontos
  - recuperação = maior entre rec por atividade e rec manual; só substitui se for maior
"""


def _pontos_melhor(info: dict | None) -> float | None:
    """Maior pontuação (em pontos) entre as tentativas concluídas de uma atividade.

    Retorna None se não houver tentativa concluída (atividade não realizada).
    """
    if not info:
        return None
    valor = float(info.get("valor_total") or 0)
    melhor = None
    for t in info.get("tentativas") or []:
        if not t.get("concluida"):
            continue
        nf = t.get("nota_final")
        if nf is not None:
            pontos = float(nf)
        elif valor > 0 and t.get("score_max"):
            pontos = float(t.get("score_raw", 0)) / float(t["score_max"]) * valor
        elif valor > 0:
            pontos = float(t.get("score_percentual", 0)) / 100.0 * valor
        else:
            pontos = 0.0
        if melhor is None or pontos > melhor:
            melhor = pontos
    return melhor


def _nota_atividade_10(info: dict | None) -> float | None:
    """Nota 0–10 de uma única atividade (melhor tentativa). None se não realizada."""
    if not info:
        return None
    valor = float(info.get("valor_total") or 0)
    if valor <= 0:
        return None
    pontos = _pontos_melhor(info)
    if pontos is None:
        return None
    return round(pontos / valor * 10, 1)


def _valor_recuperacao(rec_atividade_id, rec_nota_manual, tentativas_por_atividade) -> float | None:
    """Valor da recuperação: maior entre a nota da atividade de rec e a nota manual.

    Retorna None se nenhuma das duas fontes existir/produzir nota.
    """
    candidatos = []
    if rec_atividade_id:
        nota = _nota_atividade_10(tentativas_por_atividade.get(rec_atividade_id))
        if nota is not None:
            candidatos.append(nota)
    if rec_nota_manual is not None and rec_nota_manual != "":
        try:
            candidatos.append(round(float(rec_nota_manual), 1))
        except (TypeError, ValueError):
            pass
    return max(candidatos) if candidatos else None


def nota_unidade(unidade: dict, tentativas_por_atividade: dict) -> float:
    """Nota da unidade (0–10): soma de pontos / soma de valores_total × 10.

    Atividade não realizada conta 0. Usa a melhor tentativa de cada atividade.
    """
    soma_pontos = 0.0
    soma_valor = 0.0
    for aid in unidade.get("atividades") or []:
        info = tentativas_por_atividade.get(aid)
        if not info:
            continue
        valor = float(info.get("valor_total") or 0)
        if valor <= 0:
            continue
        soma_valor += valor
        pontos = _pontos_melhor(info)
        soma_pontos += pontos if pontos is not None else 0.0
    if soma_valor <= 0:
        return 0.0
    return round(soma_pontos / soma_valor * 10, 1)


def nota_unidade_com_rec(nota_orig: float, rec_atividade_id, rec_nota_manual,
                         tentativas_por_atividade: dict) -> float:
    """Aplica recuperação da unidade: max(nota_orig, recuperação).

    Se a recuperação for vazia, mantém a nota original; se for menor, também mantém.
    """
    rec = _valor_recuperacao(rec_atividade_id, rec_nota_manual, tentativas_por_atividade)
    if rec is None:
        return nota_orig
    return max(nota_orig, rec)


def media_disciplina(notas_unidades: list) -> float:
    """Média simples das notas de unidade (já com recuperação aplicada)."""
    if not notas_unidades:
        return 0.0
    return round(sum(notas_unidades) / len(notas_unidades), 1)


def media_disciplina_com_rec_final(media_orig: float, rec_atividade_id, rec_nota_manual,
                                   tentativas_por_atividade: dict) -> float:
    """Aplica recuperação final: max(media_orig, rec_final). Vazia → mantém."""
    rec = _valor_recuperacao(rec_atividade_id, rec_nota_manual, tentativas_por_atividade)
    if rec is None:
        return media_orig
    return max(media_orig, rec)


def _situacao(media_final: float, media_orig: float, rec_final_aplicada: bool,
              media_aprovacao: float) -> str:
    """aprovado | recuperacao | reprovado.

    - aprovado: média final ≥ média de aprovação
    - recuperacao: média (sem rec final) abaixo da aprovação e rec final ainda não lançada
    - reprovado: abaixo da aprovação mesmo após rec final (ou rec final já lançada e insuficiente)
    """
    if media_final >= media_aprovacao:
        return "aprovado"
    if not rec_final_aplicada and media_orig < media_aprovacao:
        return "recuperacao"
    return "reprovado"


def calcular_boletim_aluno(boletim: dict, unidades: list, rec_finais: list,
                           tentativas_por_atividade: dict, disciplinas: list) -> dict:
    """Boletim de um aluno: { disciplina_id: {unidades, media, rec_final, media_final, situacao} }."""
    media_aprov = float(boletim.get("media_aprovacao") or 5.0)
    disc_map = {d["id"]: d for d in disciplinas}
    rec_final_map = {rf.get("disciplina"): rf for rf in rec_finais}

    # agrupa unidades por disciplina
    por_disc: dict[str, list] = {}
    for u in unidades:
        por_disc.setdefault(u.get("disciplina"), []).append(u)

    resultado: dict[str, dict] = {}
    for disc_id, lista in por_disc.items():
        linhas = []
        for u in sorted(lista, key=lambda x: x.get("numero", 0)):
            nota = nota_unidade(u, tentativas_por_atividade)
            rec_val = _valor_recuperacao(u.get("rec_atividade"), u.get("rec_nota_manual"),
                                         tentativas_por_atividade)
            nota_final_u = nota if rec_val is None else max(nota, rec_val)
            realizada = any(
                _pontos_melhor(tentativas_por_atividade.get(aid)) is not None
                for aid in (u.get("atividades") or [])
            )
            linhas.append({
                "numero": u.get("numero"),
                "titulo": u.get("titulo") or f"Unidade {u.get('numero')}",
                "nota": nota,
                "rec": rec_val,
                "nota_final": nota_final_u,
                "realizada": realizada,
            })

        media = media_disciplina([l["nota_final"] for l in linhas])
        rf = rec_final_map.get(disc_id)
        rec_final_val = None
        if rf:
            rec_final_val = _valor_recuperacao(rf.get("rec_atividade"), rf.get("rec_nota_manual"),
                                               tentativas_por_atividade)
        media_final = media if rec_final_val is None else max(media, rec_final_val)
        situacao = _situacao(media_final, media, rec_final_val is not None, media_aprov)

        resultado[disc_id] = {
            "disciplina": disc_map.get(disc_id, {"id": disc_id, "nome": disc_id}),
            "unidades": linhas,
            "media": media,
            "rec_final": rec_final_val,
            "media_final": media_final,
            "situacao": situacao,
        }
    return resultado


def calcular_boletim_turma(boletim: dict, unidades: list, rec_finais: list,
                           todos_tentativas: list, alunos: list,
                           disciplinas: list, atividades_map: dict) -> dict:
    """Boletim de todos os alunos: { aluno_id: calcular_boletim_aluno(...) }.

    todos_tentativas: lista de registros-pai de tentativa (concluída) da turma.
    alunos: lista de {id/aluno_id, nome}. atividades_map: {atividade_id: {valor_total}}.
    """
    # agrupa tentativas por aluno e por atividade
    por_aluno: dict[str, dict] = {}
    for t in todos_tentativas:
        aid = t.get("atividade")
        alid = t.get("aluno_id")
        if not aid or not alid:
            continue
        tpa = por_aluno.setdefault(alid, {})
        if aid not in tpa:
            tpa[aid] = {
                "valor_total": (atividades_map.get(aid) or {}).get("valor_total") or 0,
                "tentativas": [],
            }
        tpa[aid]["tentativas"].append(t)

    resultado: dict[str, dict] = {}
    for aluno in alunos:
        alid = aluno.get("aluno_id") or aluno.get("id")
        tpa = por_aluno.get(alid, {})
        resultado[alid] = calcular_boletim_aluno(boletim, unidades, rec_finais, tpa, disciplinas)
    return resultado
