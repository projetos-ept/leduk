"""Envio de email transacional via Resend API.

A chave vem de RESEND_API_KEY (nunca hardcodar). Sem chave, o envio é um no-op
que retorna False — o chamador trata como best-effort (não quebra o fluxo).
"""
import os

import requests

RESEND_URL = "https://api.resend.com/emails"
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = "onboarding@resend.dev"
FROM_NAME = "LeDuk"


def _enviar(para: str, assunto: str, corpo_html: str) -> bool:
    if not RESEND_KEY:
        return False
    try:
        r = requests.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {RESEND_KEY}"},
            json={
                "from": f"{FROM_NAME} <{FROM_EMAIL}>",
                "to": [para],
                "subject": assunto,
                "html": corpo_html,
            },
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


def email_boas_vindas(para: str, nome: str, senha_temporaria: str,
                      turma_nome: str, portal_url: str) -> bool:
    html = f"""
    <h2>Bem-vindo ao LeDuk, {nome}!</h2>
    <p>Sua conta foi criada para a turma <strong>{turma_nome}</strong>.</p>
    <p><strong>Email:</strong> {para}<br>
       <strong>Senha:</strong> {senha_temporaria}</p>
    <p><a href="{portal_url}">Acessar o LeDuk &rarr;</a></p>
    <p style="color:#888;font-size:12px">
      Recomendamos alterar sua senha após o primeiro acesso.</p>
    """
    return _enviar(para, "Bem-vindo ao LeDuk — seus dados de acesso", html)


def email_redefinir_senha(para: str, nome: str, link: str) -> bool:
    html = f"""
    <h2>Redefinição de senha — LeDuk</h2>
    <p>Olá, {nome}.</p>
    <p>Foi solicitada a redefinição da sua senha.</p>
    <p><a href="{link}">Clique aqui para definir uma nova senha &rarr;</a></p>
    <p>Este link expira em <strong>24 horas</strong>.</p>
    <p style="color:#888;font-size:12px">
      Se você não solicitou isso, ignore este email.</p>
    """
    return _enviar(para, "Redefinição de senha — LeDuk", html)
