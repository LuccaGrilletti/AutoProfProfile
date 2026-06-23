from openpyxl import Workbook

from src.ingestao import COLUNAS_ANOS, TurmaAlvo, carregar_planilha

CABECALHO = ["login", "turma", "periodo"] + [nome for nome, _ano, _seg in COLUNAS_ANOS]


def _escrever_planilha(caminho, linhas: list[dict]):
    """Escreve um xlsx; cada linha é um dict {coluna: valor} (faltantes ficam vazios)."""
    workbook = Workbook()
    planilha = workbook.active
    planilha.append(CABECALHO)
    for linha in linhas:
        planilha.append([linha.get(coluna, "") for coluna in CABECALHO])
    workbook.save(caminho)


def _linha(login, turma, periodo, anos_sim=()):
    """Monta um dict de linha marcando "Sim" nas colunas de ano indicadas."""
    linha = {"login": login, "turma": turma, "periodo": periodo}
    for nome in anos_sim:
        linha[nome] = "Sim"
    return linha


def test_carregar_uma_linha_varios_anos(tmp_path):
    caminho = tmp_path / "input.xlsx"
    _escrever_planilha(caminho, [
        _linha("mirela.godoy", "G", "Matutino", ["5° EF", "6° EF", "7° EF", "1° EM", "3° EM"]),
    ])
    profs = carregar_planilha(caminho)
    assert len(profs) == 1
    prof = profs[0]
    assert prof.login == "mirela.godoy"
    assert len(prof.turmas) == 5
    assert TurmaAlvo(5, "EF", "G", "Matutino") in prof.turmas
    assert TurmaAlvo(1, "EM", "G", "Matutino") in prof.turmas


def test_sim_variacoes_e_vazio_nao_conta(tmp_path):
    caminho = tmp_path / "input.xlsx"
    _escrever_planilha(caminho, [{
        "login": "a.prof", "turma": "B", "periodo": "Vespertino",
        "5° EF": "  sim  ",   # espaços + minúsculo
        "6° EF": "SIM",       # maiúsculo
        "7° EF": "",          # vazio → não conta
        "8° EF": "Não",       # texto diferente → não conta
    }])
    turmas = carregar_planilha(caminho)[0].turmas
    assert TurmaAlvo(5, "EF", "B", "Vespertino") in turmas
    assert TurmaAlvo(6, "EF", "B", "Vespertino") in turmas
    assert TurmaAlvo(7, "EF", "B", "Vespertino") not in turmas
    assert TurmaAlvo(8, "EF", "B", "Vespertino") not in turmas
    assert len(turmas) == 2


def test_agrupa_por_login_union_sem_duplicatas(tmp_path):
    caminho = tmp_path / "input.xlsx"
    _escrever_planilha(caminho, [
        _linha("dup.prof", "G", "Matutino", ["5° EF"]),
        _linha("dup.prof", "H", "Vespertino", ["6° EF"]),
        _linha("dup.prof", "G", "Matutino", ["5° EF"]),  # duplicata exata
    ])
    profs = carregar_planilha(caminho)
    assert len(profs) == 1
    turmas = profs[0].turmas
    assert TurmaAlvo(5, "EF", "G", "Matutino") in turmas
    assert TurmaAlvo(6, "EF", "H", "Vespertino") in turmas
    assert len(turmas) == 2  # união, sem duplicar a turma repetida


def test_linha_sem_login_ignorada(tmp_path):
    caminho = tmp_path / "input.xlsx"
    _escrever_planilha(caminho, [_linha("", "G", "Matutino", ["5° EF"])])
    assert carregar_planilha(caminho) == []
