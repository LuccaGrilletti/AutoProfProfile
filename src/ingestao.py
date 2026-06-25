"""Ingestão da planilha de entrada → dataclasses de atribuição.

Uma linha por professor; linhas com o mesmo login são unidas (union de turmas, sem duplicatas).
As matérias NÃO vêm da planilha — são derivadas do Gestor de Classes em runtime.
"""

from dataclasses import dataclass, field
import src.config as config
import openpyxl

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


def carregar_planilha(caminho: str) -> list[AtribuicaoProfessor]:
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    ws = wb["professores"]
    agrupado: dict[str, list[TurmaAlvo]] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        login, turma, periodo = row[0], row[1], row[2]
        if not login or not turma or not periodo:
            continue
        login, turma, periodo = str(login).strip(), str(turma).strip(), str(periodo).strip()
        turmas = agrupado.setdefault(login, [])
        for ano, segmento in config.ANOS_FIXOS:
            turmas.append(TurmaAlvo(ano=ano, segmento=segmento,
                                    turma=turma, periodo=periodo))
    wb.close()
    return [AtribuicaoProfessor(login=login, turmas=turmas)
            for login, turmas in agrupado.items()]


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

MATERIAS_PADRAO: list[tuple[str, str]] = [
    ("Língua Portuguesa", "1º ano EF AI"),
    ("Matemática", "1º ano EF AI"),
    ("Inglês", "1º ano EF AI"),
    ("Bilingual Education", "1º ano EF AI"),
    ("Língua Portuguesa", "5º ano EF AI"),
    ("Matemática", "5º ano EF AI"),
    ("Ciências", "5º ano EF AI"),
    ("Geografia", "5º ano EF AI"),
    ("História", "5º ano EF AI"),
    ("Arte", "5º ano EF AI"),
    ("Bilingual Education", "5º ano EF AI"),
    ("Língua Portuguesa", "6º ano EF AF"),
    ("Matemática", "6º ano EF AF"),
    ("Ciências", "6º ano EF AF"),
    ("História", "6º ano EF AF"),
    ("Arte", "6º ano EF AF"),
    ("Inglês", "6º ano EF AF"),
    ("Bilingual Education", "6º ano EF AF"),
    ("Ciências", "7º ano EF AF"),
    ("Matemática", "1º ano EM"),
    ("Geografia", "1º ano EM"),
    ("História", "1º ano EM"),
    ("Sociologia", "1º ano EM"),
    ("Filosofia", "1º ano EM"),
    ("Física", "1º ano EM"),
    ("Química", "1º ano EM"),
    ("Biologia", "1º ano EM"),
    ("Arte", "1º ano EM"),
    ("Inglês", "1º ano EM"),
    ("Gramática", "1º ano EM"),
    ("Literatura", "1º ano EM"),
    ("Bilingual Education", "1º ano EM"),
    ("Matemática", "3º ano EM"),
    ("Ciências", "3º ano EM"),
    ("Geografia", "3º ano EM"),
    ("História", "3º ano EM"),
    ("Sociologia", "3º ano EM"),
    ("Filosofia", "3º ano EM"),
    ("Física", "3º ano EM"),
    ("Química", "3º ano EM"),
    ("Biologia", "3º ano EM"),
    ("Arte", "3º ano EM"),
    ("Inglês", "3º ano EM"),
    ("Gramática", "3º ano EM"),
    ("Literatura", "3º ano EM"),
    ("Bilingual Education", "3º ano EM"),
]

def carregar_materias(caminho: str) -> list[tuple[str, str]]:
    """Lê a aba Materias da planilha → [(nome_materia, serie)].
    Se a aba não existir, retorna a lista padrão hardcoded.
    """
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    if "Materias" not in wb.sheetnames:
        wb.close()
        return MATERIAS_PADRAO
    ws = wb["Materias"]
    materias = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        nome, serie = row[0], row[1]
        if nome and serie:
            materias.append((str(nome).strip(), str(serie).strip()))
    wb.close()
    return materias if materias else MATERIAS_PADRAO