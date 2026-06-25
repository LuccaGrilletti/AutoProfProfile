# ADR-005 — Matching tolerante de classes

**Status:** Aceito — a parte de *validação* foi revista pela ADR-009 (validação por toast, não por
releitura).

## Contexto

O texto de uma classe aparece em formatos diferentes em cada lugar: no GC (`"5º ano EFAI Turma G
- Matutino"`), no perfil do CENSO em modo leitura (`grado` + `grupo`, ex.: `"7° ano EF AF Turma G
- Matutino"`) e nas opções do dropdown de edição. A planilha, por sua vez, descreve a turma de
forma canônica (`ano`, `segmento`, `turma`, `período`). Comparar esses textos por igualdade
quebra.

## Decisão

1. **Uma função de correspondência, `matching.classe_bate`**, tolerante às variações: extrai
   ano (primeiro número) e segmento (`EM` se presente, senão `EF`), checa presença de
   `"Turma {letra}"` e do período. É usada em dois pontos no fluxo v1 — calcular o delta de turmas
   e selecionar a opção certa no dropdown de edição. (A inspeção do GC pelo `harvester` também a
   usa para filtrar classes relevantes.)
2. **Delta de turmas por matching, não por subtração de strings:** uma turma-alvo "já existe" se
   *alguma* linha atual do perfil satisfaz `classe_bate(linha, alvo)`.
3. **Comparação de matérias** com normalização apenas de espaços (`strip` + colapso). Normalização
   semântica de nome de matéria e aliases de período (MAT/VES) ficam **fora de escopo** por ora.

> A validação do que persistiu (antes descrita aqui como "releitura pós-save") foi substituída pela
> confirmação por toast durante a escrita — ver **ADR-009**.

## Consequências

- **+** Robusto às variações de texto do portal entre telas.
- **−** Heurísticas (ex.: `"Turma G"` por substring) podem casar errado em nomenclaturas atípicas;
  se aparecerem, restringir o critério.
- **−** Sem aliases de período: um período escrito de forma diferente do esperado não casa (decisão
  consciente até validação com dados reais).
