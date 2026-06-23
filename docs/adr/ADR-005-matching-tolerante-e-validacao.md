# ADR-005 — Matching tolerante de classes e validação pós-save

**Status:** Aceito

## Contexto

O texto de uma classe aparece em formatos diferentes em cada lugar: no GC (`"5º ano EFAI Turma G
- Matutino"`), no perfil do CENSO em modo leitura (`grado` + `grupo`, ex.: `"7° ano EF AF Turma G
- Matutino"`) e nas opções do dropdown de edição. A planilha, por sua vez, descreve a turma de
forma canônica (`ano`, `segmento`, `turma`, `período`). Comparar esses textos por igualdade
quebra.

Além disso, o portal **não emite confirmação** ao salvar.

## Decisão

1. **Uma função de correspondência, `matching.classe_bate`**, tolerante às variações: extrai
   ano (primeiro número) e segmento (`EM` se presente, senão `EF`), checa presença de
   `"Turma {letra}"` e do período. É usada nos três pontos — derivar matérias do GC, calcular o
   delta de turmas e selecionar a opção no dropdown.
2. **Delta de turmas por matching, não por subtração de strings:** uma turma-alvo "já existe" se
   *alguma* linha atual do perfil satisfaz `classe_bate(linha, alvo)`.
3. **Comparação de matérias** com normalização apenas de espaços (`strip` + colapso). Normalização
   semântica de nome de matéria e aliases de período (MAT/VES) ficam **fora de escopo** por ora.
4. **Validação pós-save:** após salvar, o perfil é **recarregado** e relido; o que não persistiu
   marca o professor como `parcial` (candidato a retry). Isso substitui o toast inexistente.

## Consequências

- **+** Robusto às variações de texto do portal entre telas.
- **+** A validação por releitura confirma a persistência real (server-side), não só o clique.
- **−** Heurísticas (ex.: `"Turma G"` por substring) podem casar errado em nomenclaturas atípicas;
  se aparecerem, restringir o critério.
- **−** Sem aliases de período: um período escrito de forma diferente do esperado não casa (decisão
  consciente até validação com dados reais).
