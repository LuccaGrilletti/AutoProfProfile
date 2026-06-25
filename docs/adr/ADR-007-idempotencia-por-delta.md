# ADR-007 — Idempotência por delta (ler estado → escrever só o que falta)

**Status:** Aceito

## Contexto

A automação escreve no perfil de cada professor (turmas e matérias). Ela é operada manualmente,
pode ser interrompida no meio, e os professores com pendência são reprocessados (ADR-008). Se cada
execução simplesmente "adicionasse tudo", haveria risco de duplicatas, erros ao reinserir o que já
existe e dificuldade de rodar de novo com segurança.

## Decisão

`perfil.processar_professor` sempre **lê o estado atual** do perfil antes de escrever e calcula o
**delta**:

1. Lê as turmas e matérias já presentes no CENSO (Fases 2b/3).
2. Compara com o alvo via `matching.classe_bate` (turmas) e comparação normalizada (matérias).
3. Escreve **apenas** o que falta. Se nada falta, o status é `ja_configurado` e nada é tocado.

Como o estado é relido a cada chamada, rodar a função várias vezes converge: o delta encolhe até
zero. Não há estado persistido entre execuções — a fonte de verdade é sempre o próprio portal.

## Consequências

- **+** Reexecução segura: re-rodar tudo (ou só os pendentes) nunca duplica.
- **+** Habilita a fila de retry (ADR-008) sem lógica extra de "o que já fiz".
- **+** Resiliente a edições manuais feitas no portal entre execuções.
- **−** Cada professor paga uma leitura do perfil antes de escrever (custo aceitável na escala atual).
