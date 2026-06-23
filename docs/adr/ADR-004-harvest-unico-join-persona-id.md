# ADR-004 — Harvest único do GC e join por Persona ID

**Status:** Aceito

## Contexto

Para saber as matérias de cada professor, é preciso ler o Gestor de Classes (GC), que mapeia
classe → matérias → professores. Ler o GC é caro (centenas de classes, duas navegações por
classe). Já o perfil no CENSO é localizado pelo **login** do professor, que retorna o **Persona
ID**. As matérias precisam ser cruzadas entre os dois sistemas.

## Decisão

1. **Harvest único:** `harvest_gc()` é chamado **uma vez** por execução e produz o mapa
   `persona_id → [ClasseGC]`, reutilizado para todos os professores.
2. **Join por Persona ID:** confirmado com o operador que o Persona ID da tabela de participantes
   do GC é **o mesmo** retornado pela busca do CENSO. O cruzamento é feito por esse ID (sem
   fallback por nome).

Fluxo: a busca no CENSO (pelo login) dá o `persona_id`; com ele, buscamos no mapa do GC as classes
do professor e derivamos as matérias.

## Consequências

- **+** Uma leitura cara do GC amortizada entre todos os professores.
- **+** Join determinístico e simples por ID.
- **−** Depende da igualdade do Persona ID nos dois sistemas; se algum dia divergir, será preciso
  reintroduzir um casamento por nome normalizado.
- **−** O mapa vive em memória durante toda a execução (aceitável para a escala atual).
