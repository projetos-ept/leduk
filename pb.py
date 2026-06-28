"""Cliente HTTP mínimo para a API do PocketBase."""
import requests


class PocketBaseClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = self.token
        return h

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = requests.get(f"{self.base_url}{path}", headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict) -> dict:
        resp = requests.post(f"{self.base_url}{path}", headers=self._headers(), json=data)
        resp.raise_for_status()
        return resp.json()

    # --- Collections ---

    def buscar_questao(self, questao_id: str) -> dict:
        questao = self._get(f"/api/collections/questoes/records/{questao_id}")
        tipo = questao.get("tipo", "")
        if tipo in ("mc4", "mc5"):
            result = self._get(
                "/api/collections/alternativas/records",
                params={"filter": f'questao="{questao_id}"', "sort": "letra"},
            )
            questao["alternativas"] = result.get("items", [])
        elif tipo == "vf":
            result = self._get(
                "/api/collections/itens_vf/records",
                params={"filter": f'questao="{questao_id}"', "sort": "ordem"},
            )
            questao["itens_vf"] = result.get("items", [])
        elif tipo == "associativa":
            result = self._get(
                "/api/collections/pares_associativos/records",
                params={"filter": f'questao="{questao_id}"', "sort": "ordem"},
            )
            questao["pares_associativos"] = result.get("items", [])
        return questao

    def buscar_atividade(self, ativ_id: str) -> dict:
        return self._get(f"/api/collections/atividades/records/{ativ_id}")

    def buscar_turma(self, turma_id: str) -> dict:
        return self._get(f"/api/collections/turmas/records/{turma_id}")

    def buscar_disciplina(self, disciplina_id: str) -> dict:
        return self._get(f"/api/collections/disciplinas/records/{disciplina_id}")

    def listar_turmas(self) -> list:
        result = self._get("/api/collections/turmas/records", params={"sort": "nome"})
        return result.get("items", [])

    def listar_atividades_por_disciplina(self, turma_id: str, disciplina_id: str) -> list:
        result = self._get(
            "/api/collections/atividades/records",
            params={
                "filter": f'turma="{turma_id}"&&disciplina="{disciplina_id}"&&ativa=true',
                "sort": "titulo",
            },
        )
        return result.get("items", [])

    def listar_materiais(self, turma_id: str, disciplina_id: str) -> list:
        result = self._get(
            "/api/collections/materiais/records",
            params={
                "filter": f'turma="{turma_id}"&&disciplina="{disciplina_id}"&&ativo=true',
                "sort": "ordem",
            },
        )
        return result.get("items", [])

    def listar_atividades_por_turma(self, turma_id: str) -> list:
        result = self._get(
            "/api/collections/atividades/records",
            params={
                "filter": f'turma="{turma_id}"&&ativa=true',
                "expand": "disciplina",
                "sort": "titulo",
            },
        )
        return result.get("items", [])

    def login_aluno(self, email: str, senha: str) -> dict:
        """POST /api/collections/users/auth-with-password → {token, record}."""
        return self._post(
            "/api/collections/users/auth-with-password",
            {"identity": email, "password": senha},
        )

    def get_aluno(self, token: str) -> dict:
        """GET /api/collections/users/records/me com token do aluno."""
        resp = requests.get(
            f"{self.base_url}/api/collections/users/records/me",
            headers={"Authorization": token, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    def registrar_tentativa(self, dados: dict) -> dict:
        return self._post("/api/collections/tentativas/records", dados)

    def tentativas_por_atividade(self, ativ_id: str, aluno_id: str) -> list:
        result = self._get(
            "/api/collections/tentativas/records",
            params={"filter": f'aluno_id="{aluno_id}"&&disciplina="{ativ_id}"'},
        )
        return result.get("items", [])
