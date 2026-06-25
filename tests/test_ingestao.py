"""Testes da ingestão da planilha (carregar_planilha).

Cobrem o comportamento da v1: cada linha (login/turma/periodo) gera uma TurmaAlvo para cada ano de
config.ANOS_FIXOS; as colunas de ano da planilha são ignoradas (ver ADR-006).
"""

from openpyxl import Workbook

from src.config import ANOS_FIXOS
from src.ingestao import COLUNAS_ANOS, TurmaAlvo, carregar_planilha

CABECALHO = ["login", "turma", "periodo"] + [nome for nome, _ano, _seg in COLUNAS_ANOS]


def _escrever_planilha(caminho, linhas: list[dict]):
    """Escreve um xlsx com a aba `professores`; cada linha é um dict {coluna: valor}."""
    workbook = Workbook()
    planilha = workbook.active
    planilha.title = "professores"
    planilha.append(CABECALHO)
    for linha in linhas:
        planilha.append([linha.get(coluna, "") for coluna in CABECALHO])
    workbook.save(caminho)


def _linha(login, turma, periodo, anos_sim=()):
    """Monta um dict de linha; `anos_sim` marca "Sim" em colunas de ano (ignoradas na v1)."""
    linha = {"login": login, "turma": turma, "periodo": periodo}
    for nome in anos_sim:
        linha[nome] = "Sim"
    return linha


def test_uma_linha_gera_todos_os_anos_fixos(tmp_path):
    caminho = tmp_path / "input.xlsx"
    _escrever_planilha(caminho, [_linha("mirela.godoy", "G", "Matutino")])
    profs = carregar_planilha(caminho)
    assert len(profs) == 1
    prof = profs[0]
    assert prof.login == "mirela.godoy"
    # uma TurmaAlvo por ano de ANOS_FIXOS, todas com a turma/período da linha
    assert len(prof.turmas) == len(ANOS_FIXOS)
    esperado = {TurmaAlvo(ano, seg, "G", "Matutino") for ano, seg in ANOS_FIXOS}
    assert set(prof.turmas) == esperado


def test_colunas_de_ano_sao_ignoradas(tmp_path):
    caminho = tmp_path / "input.xlsx"
    # mesmo sem nenhum "Sim", a linha gera todos os ANOS_FIXOS — as colunas de ano não são lidas
    sem_sim = carregar_planilha(_arquivo(tmp_path, "a", [_linha("a.prof", "B", "Vespertino")]))
    com_sim = carregar_planilha(
        _arquivo(tmp_path, "b", [_linha("a.prof", "B", "Vespertino", ["5° EF", "9° EF"])]))
    assert {t for t in sem_sim[0].turmas} == {t for t in com_sim[0].turmas}
    assert len(sem_sim[0].turmas) == len(ANOS_FIXOS)


def test_agrupa_por_login_une_as_turmas(tmp_path):
    caminho = tmp_path / "input.xlsx"
    _escrever_planilha(caminho, [
        _linha("dup.prof", "G", "Matutino"),
        _linha("dup.prof", "H", "Vespertino"),
    ])
    profs = carregar_planilha(caminho)
    assert len(profs) == 1
    turmas = set(profs[0].turmas)
    assert TurmaAlvo(5, "EF", "G", "Matutino") in turmas
    assert TurmaAlvo(1, "EM", "H", "Vespertino") in turmas
    # duas turmas/períodos × ANOS_FIXOS
    assert len(turmas) == 2 * len(ANOS_FIXOS)


def test_linha_sem_login_ignorada(tmp_path):
    caminho = tmp_path / "input.xlsx"
    _escrever_planilha(caminho, [_linha("", "G", "Matutino")])
    assert carregar_planilha(caminho) == []


def test_linha_sem_turma_ou_periodo_ignorada(tmp_path):
    caminho = tmp_path / "input.xlsx"
    _escrever_planilha(caminho, [
        _linha("a.prof", "", "Matutino"),    # sem turma
        _linha("b.prof", "G", ""),           # sem período
    ])
    assert carregar_planilha(caminho) == []


def _arquivo(tmp_path, nome, linhas):
    """Helper: escreve a planilha num arquivo nomeado e devolve o caminho (para testes que precisam de dois)."""
    caminho = tmp_path / f"input_{nome}.xlsx"
    _escrever_planilha(caminho, linhas)
    return caminho
