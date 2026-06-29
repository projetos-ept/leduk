"""Lógica pura de validação de respostas e cálculo de score."""


def validar_mc(questao: dict, resposta: str) -> dict:
    """Valida resposta de múltipla escolha (mc4 / mc5)."""
    alternativas = questao.get("alternativas", [])
    correta = next((a for a in alternativas if a.get("correta")), None)
    if correta is None:
        raise ValueError(f"Questão {questao.get('id')} sem alternativa correta definida")

    acertou = resposta.upper() == correta["letra"].upper()
    feedback = None
    if not acertou:
        selecionada = next((a for a in alternativas if a["letra"].upper() == resposta.upper()), None)
        if selecionada:
            feedback = selecionada.get("feedback")
    return {
        "correta": acertou,
        "resposta_correta": correta["letra"],
        "feedback": feedback or questao.get("feedback_geral"),
        "score_raw": int(acertou),
        "score_max": 1,
    }


def validar_vf(questao: dict, respostas: dict) -> dict:
    """Valida respostas V/F. respostas = {str(ordem): bool}."""
    itens = questao.get("itens_vf", [])
    acertos = sum(
        1 for item in itens
        if respostas.get(str(item["ordem"])) == item["gabarito"]
    )
    return {
        "correta": acertos == len(itens),
        "score_raw": acertos,
        "score_max": len(itens),
        "feedback": questao.get("feedback_geral"),
    }


def validar_associativa(questao: dict, respostas: dict) -> dict:
    """Valida pares associativos. respostas = {str(ordem): valor_coluna_b}."""
    pares = questao.get("pares_associativos", [])
    acertos = sum(
        1 for par in pares
        if respostas.get(str(par["ordem"])) == par["coluna_b"]
    )
    return {
        "correta": acertos == len(pares),
        "score_raw": acertos,
        "score_max": len(pares),
        "feedback": questao.get("feedback_geral"),
    }


def calcular_valor_ponto(atividade: dict, pesos: list) -> float:
    """Returns the value of one raw unit of score in the activity's scale.

    valor_ponto = valor_total / soma_dos_pesos
    If valor_total is not set, each raw point counts as 1.
    """
    valor_total = atividade.get("valor_total") or None
    soma = sum(float(p) for p in pesos) if pesos else 1.0
    if soma == 0:
        soma = 1.0
    return float(valor_total) / soma if valor_total else 1.0


def calcular_nota_final(respostas: list, atividade: dict) -> float | None:
    """Calculates the final grade in the activity's total-value scale.

    Each resultado in respostas must include _peso (question weight).
    Returns None if valor_total is not defined for the activity.
    Rounds to 1 decimal place.
    """
    valor_total = atividade.get("valor_total") or None
    if not valor_total:
        return None
    pesos = [float(r.get("_peso", 1)) for r in respostas]
    valor_ponto = calcular_valor_ponto(atividade, pesos)
    total = 0.0
    for r in respostas:
        peso = float(r.get("_peso", 1))
        raw = r.get("score_raw", 0) or 0
        mx = r.get("score_max", 0) or 0
        if mx > 0:
            total += (raw / mx) * peso * valor_ponto
    return round(total, 1)


def calcular_score(tipo: str, questao: dict, resposta) -> tuple[int, int]:
    """Retorna (score_raw, score_max) para qualquer tipo de questão."""
    if tipo in ("mc4", "mc5"):
        r = validar_mc(questao, resposta)
    elif tipo == "vf":
        r = validar_vf(questao, resposta)
    elif tipo == "associativa":
        r = validar_associativa(questao, resposta)
    elif tipo == "aberta":
        return 0, 0
    else:
        raise ValueError(f"Tipo de questão desconhecido: {tipo}")
    return r["score_raw"], r["score_max"]
