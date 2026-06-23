# ADR-003 — Log de execução em xlsx (sem banco de dados)

**Status:** Aceito

## Contexto

Os projetos irmãos persistem resultados em PostgreSQL (`psycopg2`). Isso exige um banco
disponível e configurado. Esta automação é operada pontualmente (início do ano letivo) e o
resultado precisa ser fácil de revisar por quem coordena — não há necessidade de consulta
relacional nem histórico em banco.

## Decisão

Registrar uma linha por operação em memória (`registro.RegistroExecucao`) e exportar tudo para
`logs/atribuicao_AAAAMMDD_HHMM.xlsx` (openpyxl) ao final da execução. Colunas: `timestamp`,
`login_professor`, `persona_id`, `fase`, `acao`, `detalhe`, `status`.

Como o portal **não dá feedback visual** (toast) ao salvar, a verdade do que foi feito é o log +
a validação pós-save (releitura do perfil) — ver ADR-005.

## Consequências

- **+** Zero dependência de banco; o artefato é um xlsx portátil, um por execução.
- **+** Fácil de abrir, filtrar e arquivar pela coordenação.
- **−** Sem histórico consolidado entre execuções (cada run é um arquivo).
- **−** O log fica em memória até o fim; uma queda abrupta perde o que não foi exportado
  (export acontece no `finally` do `main`, cobrindo erros tratados).
