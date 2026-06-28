"""Testes unitários para validação de respostas (sem rede, sem Flask)."""
import pytest
from questao import validar_mc, validar_vf, validar_associativa


class TestValidarMC:
    def test_resposta_correta(self, questao_mc4):
        r = validar_mc(questao_mc4, "A")
        assert r["correta"] is True
        assert r["score_raw"] == 1
        assert r["score_max"] == 1

    def test_resposta_errada_retorna_feedback_da_alternativa(self, questao_mc4):
        r = validar_mc(questao_mc4, "B")
        assert r["correta"] is False
        assert r["score_raw"] == 0
        assert "Chagas" in r["feedback"]

    def test_resposta_errada_sem_feedback_usa_feedback_geral(self, questao_mc4):
        # alternativa D não tem feedback específico — cai no feedback_geral
        questao_mc4["alternativas"][3]["feedback"] = None
        r = validar_mc(questao_mc4, "D")
        assert r["correta"] is False
        assert r["feedback"] == questao_mc4["feedback_geral"]

    def test_case_insensitive(self, questao_mc4):
        assert validar_mc(questao_mc4, "a")["correta"] is True

    def test_sem_alternativa_correta_levanta_erro(self, questao_mc4):
        for alt in questao_mc4["alternativas"]:
            alt["correta"] = False
        with pytest.raises(ValueError, match="sem alternativa correta"):
            validar_mc(questao_mc4, "A")


class TestValidarVF:
    def test_todas_certas(self, questao_vf):
        respostas = {"1": True, "2": False, "3": True}
        r = validar_vf(questao_vf, respostas)
        assert r["correta"] is True
        assert r["score_raw"] == 3
        assert r["score_max"] == 3

    def test_parcialmente_correto(self, questao_vf):
        respostas = {"1": True, "2": True, "3": True}  # item 2 errado
        r = validar_vf(questao_vf, respostas)
        assert r["correta"] is False
        assert r["score_raw"] == 2
        assert r["score_max"] == 3

    def test_todas_erradas(self, questao_vf):
        respostas = {"1": False, "2": True, "3": False}
        r = validar_vf(questao_vf, respostas)
        assert r["score_raw"] == 0

    def test_respostas_vazias(self, questao_vf):
        r = validar_vf(questao_vf, {})
        assert r["score_raw"] == 0


class TestValidarAssociativa:
    def test_todos_corretos(self, questao_associativa):
        respostas = {
            "1": "Glicose",
            "2": "Ureia",
            "3": "Aspartato aminotransferase",
            "4": "Creatinina",
        }
        r = validar_associativa(questao_associativa, respostas)
        assert r["correta"] is True
        assert r["score_raw"] == 4
        assert r["score_max"] == 4

    def test_parcialmente_correto(self, questao_associativa):
        respostas = {
            "1": "Glicose",
            "2": "Errado",
            "3": "Aspartato aminotransferase",
            "4": "Errado",
        }
        r = validar_associativa(questao_associativa, respostas)
        assert r["score_raw"] == 2

    def test_vazio(self, questao_associativa):
        r = validar_associativa(questao_associativa, {})
        assert r["score_raw"] == 0
        assert r["correta"] is False
