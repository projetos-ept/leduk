# LeDuk — Lições aprendidas (convenções permanentes)

Este arquivo registra bugs recorrentes já resolvidos e as convenções que
evitam sua reintrodução. Qualquer agente escrevendo um novo
`scripts/migrate_*.py` ou método em `pb.py` deve consultar isto antes.

---

## 1. Campos `bool` nunca devem ser `"required": True`

**Sintoma:** PocketBase rejeita a inserção com `validation_required` mesmo
quando o campo bool foi enviado explicitamente como `false`.

**Causa:** o PocketBase trata `false` como "valor vazio" em campos bool
obrigatórios — o validador de required não distingue "ausente" de "falso".

**Regra:** todo campo `{"type": "bool", ...}` em qualquer schema criado por
`scripts/migrate_*.py` (ou em qualquer payload montado por `pb.py`) deve usar

```python
{"name": "ativo", "type": "bool", "required": False}
```

Nunca `"required": True` em campo bool — mesmo que a lógica de negócio exija
que ele sempre tenha um valor. Trate a obrigatoriedade na camada de aplicação
(Flask), não no schema do PocketBase.

**Auditoria (2026-07):** verificado todos os `scripts/migrate_*.py` e `pb.py`
existentes — nenhuma ocorrência de `bool` com `required: True`. Nenhum script
cria ou altera o schema de `alternativas` (`jf69g6b4qr80hq3`) ou `itens_vf`
(`dkc5b8csbsus7es`); essas collections foram seedadas fora deste conjunto de
scripts. Se um script futuro precisar tocar essas collections, aplicar a
mesma regra aos campos `correta`/`gabarito`.

---

## 2. Regras de acesso vão no payload de criação, nunca em PATCH posterior

**Sintoma:** collection criada por migração fica admin-only até alguém
liberar manualmente pelo painel do PocketBase.

**Causa:** o PocketBase cria collections com `listRule`/`viewRule`/etc. como
`null` (admin-only) por padrão, se o payload de criação não especificar.

**Regra:** todo `POST /api/collections` deve incluir as regras no mesmo
payload:

```python
"listRule": "", "viewRule": "",
"createRule": '@request.auth.id != ""',
"updateRule": '@request.auth.id != ""',
"deleteRule": '@request.auth.id != ""',
```

Exceções documentadas (regras próprias, não seguem o padrão acima):
`tentativas` (escrita pública, para o aluno enviar respostas sem custom auth
adicional) e `tokens_senha` (`createRule`/`updateRule` públicos, necessários
para o fluxo de redefinição de senha sem login).

Ver `README.md` → "Regras de acesso (listRule / viewRule)" para a tabela
completa por collection.

---

## 3. Ordem de criação das collections

O PocketBase rejeita campos `relation` apontando para collections que ainda
não existem. Toda migração que cria uma collection com relation deve
resolver o ID da collection-alvo **em runtime** (via `GET /api/collections/<nome>`)
em vez de hardcodar — e a documentação da ordem de dependências fica em
`README.md` → "Ordem de criação obrigatória".

---

## 4. Migrações devem ser idempotentes

Todo `scripts/migrate_*.py` verifica se a collection/campo já existe antes de
criar (`get_collection(token, nome)` retornando `None` em 404) e imprime
`[OK] ... já existe` em vez de falhar. Isso permite rodar o mesmo script
várias vezes em produção sem efeito colateral.
