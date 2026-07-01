"""Testes do envio de email (Resend mockado)."""
from unittest.mock import patch

import utils.email as email_mod


def test_boas_vindas_chama_resend_com_payload():
    with patch.object(email_mod, "RESEND_KEY", "re_test"), \
         patch.object(email_mod.requests, "post") as mock_post:
        mock_post.return_value.status_code = 200
        ok = email_mod.email_boas_vindas("a@x.com", "João", "senha123",
                                         "5TACN1", "https://leduk.test")
        assert ok is True
        args, kwargs = mock_post.call_args
        assert args[0] == email_mod.RESEND_URL
        body = kwargs["json"]
        assert body["to"] == ["a@x.com"]
        assert "dados de acesso" in body["subject"]
        assert "senha123" in body["html"] and "5TACN1" in body["html"]
        assert kwargs["headers"]["Authorization"] == "Bearer re_test"


def test_redefinir_chama_resend_com_link():
    with patch.object(email_mod, "RESEND_KEY", "re_test"), \
         patch.object(email_mod.requests, "post") as mock_post:
        mock_post.return_value.status_code = 200
        ok = email_mod.email_redefinir_senha("a@x.com", "João", "https://leduk.test/r/abc")
        assert ok is True
        body = mock_post.call_args.kwargs["json"]
        assert "https://leduk.test/r/abc" in body["html"]
        assert "Redefinição" in body["subject"]


def test_retorna_false_sem_chave():
    with patch.object(email_mod, "RESEND_KEY", ""), \
         patch.object(email_mod.requests, "post") as mock_post:
        assert email_mod.email_boas_vindas("a@x.com", "J", "s", "T", "u") is False
        mock_post.assert_not_called()


def test_retorna_false_em_erro_http():
    with patch.object(email_mod, "RESEND_KEY", "re_test"), \
         patch.object(email_mod.requests, "post") as mock_post:
        mock_post.return_value.status_code = 422
        assert email_mod.email_redefinir_senha("a@x.com", "J", "l") is False
