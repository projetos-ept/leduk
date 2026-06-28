"""Testes unitários para a função calcular_score."""
import pytest
from questao import calcular_score


class TestCalcularScore:
    def test_mc4_acerto(self, questao_mc4):
        raw, mx = calcular_score("mc4", questao_mc4, "A")
        assert (raw, mx) == (1, 1)

    def test_mc4_erro(self, questao_mc4):
        raw, mx = calcular_score("mc4", questao_mc4, "B")
        assert (raw, mx) == (0, 1)

    def test_mc5_alias(self, questao_mc4):
        # mc5 usa o mesmo validador que mc4
        questao_mc4["tipo"] = "mc5"
        raw, mx = calcular_score("mc5", questao_mc4, "A")
        assert raw == 1

    def test_vf_score_parcial(self, questao_vf):
        respostas = {"1": True, "2": True, "3": True}  # item 2 esperava False
        raw, mx = calcular_score("vf", questao_vf, respostas)
        assert raw == 2
        assert mx == 3

    def test_associativa_score_total(self, questao_associativa):
        respostas = {
            "1": "Glicose",
            "2": "Ureia",
            "3": "Aspartato aminotransferase",
            "4": "Creatinina",
        }
        raw, mx = calcular_score("associativa", questao_associativa, respostas)
        assert (raw, mx) == (4, 4)

    def test_aberta_score_zero(self, questao_mc4):
        questao_mc4["tipo"] = "aberta"
        raw, mx = calcular_score("aberta", questao_mc4, "dissertação livre")
        assert (raw, mx) == (0, 0)

    def test_tipo_desconhecido_levanta_erro(self, questao_mc4):
        with pytest.raises(ValueError, match="Tipo de questão desconhecido"):
            calcular_score("invalido", questao_mc4, "X")
