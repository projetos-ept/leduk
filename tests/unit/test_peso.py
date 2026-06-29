"""Testes unitários para calcular_valor_ponto e calcular_nota_final."""
from questao import calcular_valor_ponto, calcular_nota_final


class TestCalcularValorPonto:
    def test_dois_pesos_distintos(self):
        atividade = {"valor_total": 3.0}
        pesos = [2.0, 3.0]
        vp = calcular_valor_ponto(atividade, pesos)
        assert vp == 3.0 / 5.0

    def test_pesos_iguais_unitarios(self):
        atividade = {"valor_total": 10.0}
        pesos = [1.0, 1.0]
        vp = calcular_valor_ponto(atividade, pesos)
        assert vp == 5.0

    def test_sem_valor_total_retorna_1(self):
        atividade = {}
        pesos = [2.0, 3.0]
        vp = calcular_valor_ponto(atividade, pesos)
        assert vp == 1.0

    def test_valor_total_zero_retorna_1(self):
        atividade = {"valor_total": 0}
        pesos = [1.0]
        vp = calcular_valor_ponto(atividade, pesos)
        assert vp == 1.0

    def test_lista_vazia_nao_divide_por_zero(self):
        atividade = {"valor_total": 5.0}
        vp = calcular_valor_ponto(atividade, [])
        assert vp == 5.0


class TestCalcularNotaFinal:
    def _make_resposta(self, score_raw, score_max, peso):
        return {"score_raw": score_raw, "score_max": score_max, "_peso": peso}

    def test_acerto_total_dois_pesos(self):
        # valor_total=3, pesos=[2,3] → vp=0.6
        # Q1: 1/1 * 2 * 0.6 = 1.2  Q2: 1/1 * 3 * 0.6 = 1.8  Total=3.0
        atividade = {"valor_total": 3.0}
        respostas = [
            self._make_resposta(1, 1, 2),
            self._make_resposta(1, 1, 3),
        ]
        assert calcular_nota_final(respostas, atividade) == 3.0

    def test_erro_total(self):
        atividade = {"valor_total": 3.0}
        respostas = [
            self._make_resposta(0, 1, 2),
            self._make_resposta(0, 1, 3),
        ]
        assert calcular_nota_final(respostas, atividade) == 0.0

    def test_acerto_parcial(self):
        # valor_total=3, pesos=[2,3] → vp=0.6
        # Q1 errada: 0  Q2 certa: 1/1 * 3 * 0.6 = 1.8
        atividade = {"valor_total": 3.0}
        respostas = [
            self._make_resposta(0, 1, 2),
            self._make_resposta(1, 1, 3),
        ]
        assert calcular_nota_final(respostas, atividade) == 1.8

    def test_sem_valor_total_retorna_none(self):
        atividade = {}
        respostas = [self._make_resposta(1, 1, 1)]
        assert calcular_nota_final(respostas, atividade) is None

    def test_questao_vf_parcial(self):
        # valor_total=2, peso=1 para ambas
        # Q1 VF: 2/3 acertos  Q2 MC: 1/1 acerto
        # vp = 2/2 = 1.0
        # Q1: 2/3 * 1 * 1.0 = 0.667  Q2: 1/1 * 1 * 1.0 = 1.0  Total=1.7
        atividade = {"valor_total": 2.0}
        respostas = [
            self._make_resposta(2, 3, 1),
            self._make_resposta(1, 1, 1),
        ]
        result = calcular_nota_final(respostas, atividade)
        assert result == round(2 / 3 + 1.0, 1)

    def test_arredonda_uma_casa(self):
        atividade = {"valor_total": 10.0}
        respostas = [self._make_resposta(1, 3, 1)]
        result = calcular_nota_final(respostas, atividade)
        assert result == round(10 / 3, 1)

    def test_score_max_zero_ignorado(self):
        # Questão aberta (score_max=0) não deve contribuir para a nota
        atividade = {"valor_total": 3.0}
        respostas = [
            self._make_resposta(1, 1, 2),
            self._make_resposta(0, 0, 3),  # aberta não avaliada
        ]
        # vp = 3.0 / (2+3) = 0.6; Q1: 1/1 * 2 * 0.6 = 1.2; Q2 skipped
        result = calcular_nota_final(respostas, atividade)
        assert result == 1.2
