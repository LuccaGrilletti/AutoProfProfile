"""Ingestão da planilha de entrada → dataclasses de atribuição.

Uma linha por professor; linhas com o mesmo login são unidas (union de turmas, sem duplicatas).
As matérias NÃO vêm da planilha — são derivadas do Gestor de Classes em runtime.
"""

from dataclasses import dataclass, field

from openpyxl import load_workbook

# Mapeamento das colunas de ano da planilha para (ano, segmento).
COLUNAS_ANOS = [
    ("1° EF", 1, "EF"), ("2° EF", 2, "EF"), ("3° EF", 3, "EF"),
    ("4° EF", 4, "EF"), ("5° EF", 5, "EF"), ("6° EF", 6, "EF"),
    ("7° EF", 7, "EF"), ("8° EF", 8, "EF"), ("9° EF", 9, "EF"),
    ("1° EM", 1, "EM"), ("2° EM", 2, "EM"), ("3° EM", 3, "EM"),
]


@dataclass(frozen=True)
class TurmaAlvo:
    ano: int          # 1..9 para EF, 1..3 para EM
    segmento: str     # "EF" | "EM"
    turma: str        # letra, ex: "G"
    periodo: str      # "Matutino" | "Vespertino" | ...

    @property
    def chave_pesquisa(self) -> str:
        """Termo usado no campo de busca do perfil do professor."""
        return f"Turma {self.turma} - {self.periodo}"

    @property
    def chave_canonica(self) -> str:
        """Chave legível para logs."""
        return f"{self.ano}° {self.segmento} - Turma {self.turma} - {self.periodo}"


@dataclass
class AtribuicaoProfessor:
    login: str
    turmas: list[TurmaAlvo] = field(default_factory=list)
    # matérias NÃO entram aqui — derivadas do GC em runtime


def carregar_planilha(caminho) -> list[AtribuicaoProfessor]:
    """Lê o xlsx de entrada e retorna a lista de atribuições, agrupada por login.

    Para cada linha, cada coluna de ano marcada com "Sim" (case-insensitive, com strip) vira um
    TurmaAlvo: ano+segmento da coluna, turma+periodo da linha. Linhas com o mesmo login têm as
    turmas unidas, preservando a ordem e descartando duplicatas. Linhas sem login são ignoradas.
    """
    workbook = load_workbook(caminho, read_only=True, data_only=True)
    planilha = workbook.active
    try:
        linhas = planilha.iter_rows(values_only=True)
        try:
            cabecalho = [_texto(c) for c in next(linhas)]
        except StopIteration:
            return []

        indice = {nome: i for i, nome in enumerate(cabecalho)}
        idx_login = _indice_coluna(indice, "login")
        idx_turma = _indice_coluna(indice, "turma")
        idx_periodo = _indice_coluna(indice, "periodo")

        # login → dict[TurmaAlvo] (dict preserva ordem de inserção e evita duplicatas)
        por_login: dict[str, dict] = {}
        for linha in linhas:
            login = _celula(linha, idx_login)
            if not login:
                continue
            turma = _celula(linha, idx_turma)
            periodo = _celula(linha, idx_periodo)

            turmas = por_login.setdefault(login, {})
            for nome_coluna, ano, segmento in COLUNAS_ANOS:
                j = indice.get(nome_coluna)
                if j is None or j >= len(linha):
                    continue
                if _eh_sim(linha[j]):
                    alvo = TurmaAlvo(ano=ano, segmento=segmento, turma=turma, periodo=periodo)
                    turmas[alvo] = None
    finally:
        workbook.close()

    return [
        AtribuicaoProfessor(login=login, turmas=list(turmas))
        for login, turmas in por_login.items()
    ]


def _eh_sim(valor) -> bool:
    """True se a célula indica "Sim" (case-insensitive, ignorando espaços nas pontas)."""
    return valor is not None and str(valor).strip().lower() == "sim"


def _texto(valor) -> str:
    """Normaliza uma célula para string sem espaços nas pontas."""
    return "" if valor is None else str(valor).strip()


def _celula(linha, indice) -> str:
    """Valor textual da célula no índice dado, ou "" se índice inválido/ausente."""
    if indice is None or indice >= len(linha):
        return ""
    return _texto(linha[indice])


def _indice_coluna(indice: dict, nome: str):
    """Índice da coluna pelo nome (case-insensitive), ou None se ausente."""
    if nome in indice:
        return indice[nome]
    alvo = nome.lower()
    for chave, i in indice.items():
        if chave.lower() == alvo:
            return i
    return None
