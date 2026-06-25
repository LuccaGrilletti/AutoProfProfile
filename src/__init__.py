"""Automação de atribuição de turmas e matérias ao professor no Pegasus (CENSO).

Pacote que lê uma planilha de professores, lê o estado atual de cada perfil no CENSO e escreve
apenas o que falta (delta), de forma idempotente. Pontos de entrada executáveis:

    python -m src.main              # fluxo completo (orquestrador)
    python -m src.verificar_sessao  # smoke test da sessão CDP
    python -m src.perfil <login>    # processa um único professor (debug)
    python -m src.harvester [N]     # inspeção do Gestor de Classes (debug)

Visão geral do fluxo e decisões de arquitetura no README e em docs/adr/.
"""
