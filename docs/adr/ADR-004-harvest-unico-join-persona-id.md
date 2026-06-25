# ADR-004 — Harvest único do GC e join por Persona ID

**Status:** Aceito — parte do *harvest para derivar matérias* foi substituída pela ADR-006 no
fluxo v1; o **join por Persona ID continua válido e em uso**.

## Contexto

O perfil no CENSO é localizado pelo **login** do professor, que retorna o **Persona ID**. Para
saber as matérias de cada professor, a abordagem original lia o Gestor de Classes (GC), que mapeia
classe → matérias → professores, e cruzava os dois sistemas. Ler o GC é caro (centenas de classes,
duas navegações por classe).

## Decisão

1. **Join por Persona ID (vigente):** confirmado com o operador que o Persona ID da tabela de
   participantes do GC é **o mesmo** retornado pela busca do CENSO. A busca no CENSO (pelo login)
   dá o `persona_id`, que identifica o perfil do professor na URL. O cruzamento é por esse ID (sem
   fallback por nome). Isso é o que `perfil._buscar_persona_id` faz hoje.
2. **Harvest único para derivar matérias (legado na v1):** `harvest_gc()` produz o mapa
   `persona_id → [ClasseGC]` em uma leitura por execução. **A v1 não usa mais esse mapa** para
   alimentar o fluxo: as matérias vêm de uma lista fixa (ver ADR-006). O `harvester` permanece
   como ferramenta **ativa** de inspeção do GC (auditar contagens, validar contra o portal).

## Consequências

- **+** Join determinístico e simples por ID, sem ambiguidade de nomes.
- **+** O harvester segue útil para auditoria, mesmo fora do caminho crítico.
- **−** Depende da igualdade do Persona ID nos dois sistemas; se algum dia divergir, será preciso
  reintroduzir um casamento por nome normalizado.
- **−** Se um dia o currículo voltar a ser derivado do GC, o custo da leitura cara (e o mapa em
  memória) volta à mesa — ver os trade-offs na ADR-006.
