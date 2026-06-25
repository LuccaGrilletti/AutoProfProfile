# ADR-011 — Entrada centrada em planilha, sem banco de dados

**Status:** Aceito

## Contexto

A automação precisa de dois tipos de entrada: **parâmetros** (ids do colégio/ciclo, URLs, modo de
auth) e **dados** (quais professores processar e suas turmas). Os projetos irmãos usam PostgreSQL,
o que exige banco disponível e configurado. Esta automação roda pontualmente (início do ano letivo)
e quem a opera é coordenação pedagógica, não infra.

## Decisão

Separar entrada em duas fontes simples, sem banco:

1. **Parâmetros → `.env`** (lido só por `config.py`, fonte única de verdade): `COLEGIO_ID`,
   `CICLO_ID`, `NIVEL_ID`, URLs, `AUTH_MODE`, `RETRY_MAX`. As URLs do portal são **derivadas** desses
   valores, nunca hardcoded espalhadas.
2. **Dados → uma planilha xlsx** (`dados/input_professores.xlsx`): aba `professores` (login, turma,
   período por professor) e aba opcional `Materias` (override da lista fixa — ver ADR-006).

A saída segue o mesmo espírito: um xlsx de log por execução (ADR-003). Não há persistência de estado
entre execuções — a idempotência vem de reler o portal (ADR-007).

## Consequências

- **+** Zero infraestrutura: clonar, configurar `.env`, preencher uma planilha e rodar.
- **+** Coordenação edita a entrada e lê a saída em ferramentas que já domina (Excel).
- **+** `config.py` como ponto único evita ids/URLs duplicados pelo código.
- **−** Sem validação relacional da entrada; erros de digitação na planilha só aparecem em runtime.
- **−** Não escala para muitos colégios/execuções concorrentes — não é o caso de uso atual.
