"""Testes do módulo de cálculo de boletim — foco nas bordas de recuperação."""
from boletim import (
    nota_unidade,
    nota_unidade_com_rec,
    media_disciplina,
    media_disciplina_com_rec_final,
    calcular_boletim_aluno,
    calcular_boletim_turma,
)


def _tent(nota_final=None, concluida=True, **kw):
    return {"concluida": concluida, "nota_final": nota_final, **kw}


# ── nota_unidade ────────────────────────────────────────────────────────────────

def test_nota_unidade_9_de_15_da_6():
    # A: 6 de 10, B: 3 de 5 → 9/15 × 10 = 6.0
    tpa = {
        "a1": {"valor_total": 10, "tentativas": [_tent(6.0)]},
        "a2": {"valor_total": 5, "tentativas": [_tent(3.0)]},
    }
    u = {"atividades": ["a1", "a2"]}
    assert nota_unidade(u, tpa) == 6.0


def test_nota_unidade_atividade_nao_realizada_conta_zero():
    tpa = {
        "a1": {"valor_total": 10, "tentativas": [_tent(8.0)]},
        "a2": {"valor_total": 10, "tentativas": []},  # não realizada → 0
    }
    u = {"atividades": ["a1", "a2"]}
    assert nota_unidade(u, tpa) == 4.0  # 8 / 20 × 10


def test_nota_unidade_usa_melhor_tentativa():
    tpa = {"a1": {"valor_total": 10, "tentativas": [_tent(4.0), _tent(7.0), _tent(5.0)]}}
    assert nota_unidade({"atividades": ["a1"]}, tpa) == 7.0


def test_nota_unidade_fallback_score_percentual():
    # sem nota_final, usa score_percentual
    tpa = {"a1": {"valor_total": 10, "tentativas": [
        {"concluida": True, "nota_final": None, "score_percentual": 80, "score_max": 0}]}}
    assert nota_unidade({"atividades": ["a1"]}, tpa) == 8.0


def test_nota_unidade_sem_atividades_e_zero():
    assert nota_unidade({"atividades": []}, {}) == 0.0


# ── recuperação da unidade ──────────────────────────────────────────────────────

def test_rec_unidade_maior_substitui():
    # nota original 4.0, rec manual 6.0 → 6.0
    assert nota_unidade_com_rec(4.0, "", 6.0, {}) == 6.0


def test_rec_unidade_menor_mantem_original():
    # nota original 7.0, rec manual 5.0 → mantém 7.0
    assert nota_unidade_com_rec(7.0, "", 5.0, {}) == 7.0


def test_rec_unidade_vazia_mantem_original():
    assert nota_unidade_com_rec(5.5, "", None, {}) == 5.5
    assert nota_unidade_com_rec(5.5, "", "", {}) == 5.5


def test_rec_unidade_por_atividade():
    # rec via atividade: 9 de 10 → 9.0, maior que original 4.0
    tpa = {"rec1": {"valor_total": 10, "tentativas": [_tent(9.0)]}}
    assert nota_unidade_com_rec(4.0, "rec1", None, tpa) == 9.0


def test_rec_unidade_pega_maior_entre_atividade_e_manual():
    tpa = {"rec1": {"valor_total": 10, "tentativas": [_tent(6.0)]}}
    # rec atividade 6.0, rec manual 8.0 → usa 8.0
    assert nota_unidade_com_rec(3.0, "rec1", 8.0, tpa) == 8.0


# ── média da disciplina ─────────────────────────────────────────────────────────

def test_media_disciplina_simples():
    assert media_disciplina([7.5, 6.0, 8.0]) == 7.2


def test_media_disciplina_vazia():
    assert media_disciplina([]) == 0.0


def test_media_rec_final_maior_substitui():
    assert media_disciplina_com_rec_final(4.0, "", 6.0, {}) == 6.0


def test_media_rec_final_menor_mantem():
    assert media_disciplina_com_rec_final(7.0, "", 5.0, {}) == 7.0


def test_media_rec_final_vazia_mantem():
    assert media_disciplina_com_rec_final(6.8, "", None, {}) == 6.8


# ── calcular_boletim_aluno (estrutura + situação) ───────────────────────────────

BOLETIM = {"media_aprovacao": 5.0}
DISCIPLINAS = [{"id": "d1", "nome": "IATS"}]


def test_boletim_aluno_aprovado():
    tpa = {
        "u1a": {"valor_total": 10, "tentativas": [_tent(7.5)]},
        "u2a": {"valor_total": 10, "tentativas": [_tent(6.0)]},
        "u3a": {"valor_total": 10, "tentativas": [_tent(8.0)]},
    }
    unidades = [
        {"numero": 1, "disciplina": "d1", "atividades": ["u1a"]},
        {"numero": 2, "disciplina": "d1", "atividades": ["u2a"]},
        {"numero": 3, "disciplina": "d1", "atividades": ["u3a"]},
    ]
    r = calcular_boletim_aluno(BOLETIM, unidades, [], tpa, DISCIPLINAS)
    d = r["d1"]
    assert [l["nota_final"] for l in d["unidades"]] == [7.5, 6.0, 8.0]
    assert d["media"] == 7.2
    assert d["media_final"] == 7.2
    assert d["situacao"] == "aprovado"


def test_boletim_aluno_aprovado_via_rec_final():
    # médias baixas, mas rec final 6.0 sobe a média e aprova
    tpa = {
        "u1a": {"valor_total": 10, "tentativas": [_tent(4.0)]},
        "u2a": {"valor_total": 10, "tentativas": [_tent(5.5)]},
        "u3a": {"valor_total": 10, "tentativas": [_tent(3.0)]},
    }
    unidades = [
        {"numero": 1, "disciplina": "d1", "atividades": ["u1a"]},
        {"numero": 2, "disciplina": "d1", "atividades": ["u2a"]},
        {"numero": 3, "disciplina": "d1", "atividades": ["u3a"]},
    ]
    rec_finais = [{"disciplina": "d1", "rec_atividade": "", "rec_nota_manual": 6.0}]
    r = calcular_boletim_aluno(BOLETIM, unidades, rec_finais, tpa, DISCIPLINAS)
    d = r["d1"]
    assert d["media"] == 4.2          # (4.0+5.5+3.0)/3
    assert d["rec_final"] == 6.0
    assert d["media_final"] == 6.0
    assert d["situacao"] == "aprovado"


def test_boletim_aluno_reprovado_mesmo_com_rec():
    tpa = {
        "u1a": {"valor_total": 10, "tentativas": [_tent(3.0)]},
        "u2a": {"valor_total": 10, "tentativas": [_tent(2.0)]},
        "u3a": {"valor_total": 10, "tentativas": [_tent(1.0)]},
    }
    unidades = [
        {"numero": 1, "disciplina": "d1", "atividades": ["u1a"]},
        {"numero": 2, "disciplina": "d1", "atividades": ["u2a"]},
        {"numero": 3, "disciplina": "d1", "atividades": ["u3a"]},
    ]
    rec_finais = [{"disciplina": "d1", "rec_atividade": "", "rec_nota_manual": 4.0}]
    r = calcular_boletim_aluno(BOLETIM, unidades, rec_finais, tpa, DISCIPLINAS)
    d = r["d1"]
    assert d["media"] == 2.0
    assert d["media_final"] == 4.0     # rec sobe mas continua < 5
    assert d["situacao"] == "reprovado"


def test_boletim_aluno_em_recuperacao_quando_rec_final_pendente():
    # média abaixo da aprovação e nenhuma rec final lançada → "recuperacao"
    tpa = {"u1a": {"valor_total": 10, "tentativas": [_tent(3.0)]}}
    unidades = [{"numero": 1, "disciplina": "d1", "atividades": ["u1a"]}]
    r = calcular_boletim_aluno(BOLETIM, unidades, [], tpa, DISCIPLINAS)
    assert r["d1"]["situacao"] == "recuperacao"


def test_boletim_aluno_rec_unidade_aplicada_na_linha():
    # U1 nota 4.0, rec de unidade 7.0 → linha mostra nota_final 7.0
    tpa = {
        "u1a": {"valor_total": 10, "tentativas": [_tent(4.0)]},
        "rec1": {"valor_total": 10, "tentativas": [_tent(7.0)]},
    }
    unidades = [{"numero": 1, "disciplina": "d1", "atividades": ["u1a"],
                 "rec_atividade": "rec1", "rec_nota_manual": None}]
    r = calcular_boletim_aluno(BOLETIM, unidades, [], tpa, DISCIPLINAS)
    linha = r["d1"]["unidades"][0]
    assert linha["nota"] == 4.0
    assert linha["rec"] == 7.0
    assert linha["nota_final"] == 7.0


def test_boletim_aluno_unidade_nao_realizada_flag():
    tpa = {"u1a": {"valor_total": 10, "tentativas": []}}
    unidades = [{"numero": 1, "disciplina": "d1", "atividades": ["u1a"]}]
    r = calcular_boletim_aluno(BOLETIM, unidades, [], tpa, DISCIPLINAS)
    assert r["d1"]["unidades"][0]["realizada"] is False


# ── calcular_boletim_turma ──────────────────────────────────────────────────────

def test_boletim_turma_por_aluno():
    todos = [
        {"atividade": "u1a", "aluno_id": "al1", "concluida": True, "nota_final": 8.0},
        {"atividade": "u1a", "aluno_id": "al2", "concluida": True, "nota_final": 3.0},
    ]
    alunos = [{"aluno_id": "al1", "nome": "João"}, {"aluno_id": "al2", "nome": "Maria"}]
    unidades = [{"numero": 1, "disciplina": "d1", "atividades": ["u1a"]}]
    atividades_map = {"u1a": {"valor_total": 10}}
    r = calcular_boletim_turma(BOLETIM, unidades, [], todos, alunos, DISCIPLINAS, atividades_map)
    assert r["al1"]["d1"]["media"] == 8.0
    assert r["al1"]["d1"]["situacao"] == "aprovado"
    assert r["al2"]["d1"]["media"] == 3.0
    assert r["al2"]["d1"]["situacao"] == "recuperacao"
