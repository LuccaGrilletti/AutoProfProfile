# ADR-010 — Seletores CSS/XPath locais a cada módulo

**Status:** Aceito

## Contexto

Toda a automação depende de seletores do DOM do portal (classes do Angular Material, `data-*`,
XPaths por texto). Esses seletores são frágeis: mudam quando o portal é atualizado. Era preciso
decidir onde guardá-los — num registro central compartilhado ou junto de quem os usa.

## Decisão

Cada módulo declara, **no topo do próprio arquivo**, as constantes de seletor que usa:
`perfil.py` tem `CAMPO_LOGIN`, `ABA_TURMAS`, `COMBOBOX_SEGMENTO`, etc.; `harvester.py` tem
`SELETOR_TABELA_GC`, `SELETOR_BOTAO_PROXIMA`, etc. Não há um módulo `seletores.py` central. Cada
constante fica perto da lógica que depende dela, com um comentário quando o seletor tem uma sutileza
(ex.: `:visible` para evitar o elemento gêmeo oculto da aba inativa; dropdown do ng-select que
renderiza fora do DOM do campo).

## Consequências

- **+** Mudança na tela de perfil afeta só `perfil.py`; mudança no GC, só `harvester.py`.
- **+** O contexto do seletor (por que ele é assim) fica ao lado de quem o usa.
- **−** Seletores comuns a mais de uma tela podem ser duplicados entre módulos.
- **−** Sem um inventário único, uma reformulação global do portal exige varrer vários arquivos.
- **Nota:** há constantes de seletor declaradas mas hoje não usadas em `perfil.py` (alguns
  literais aparecem inline). Limpeza pendente, sem impacto funcional.
