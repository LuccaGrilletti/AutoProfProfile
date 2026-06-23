"""Registro de execução: acumula uma linha por operação e exporta para xlsx ao final.

Não há feedback visual (toast) no portal, então o log é a fonte de verdade do que foi feito —
uma linha por turma/matéria adicionada, ambiguidade ou erro.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

COLUNAS_LOG = ["timestamp", "login_professor", "persona_id", "fase", "acao", "detalhe", "status"]


def resumir_erro(excecao: Exception) -> str:
    """Achata e trunca a mensagem (erros do Playwright trazem call log extenso)."""
    return " ".join(str(excecao).split())[:300]


@dataclass
class RegistroExecucao:
    """Acumula linhas de log em memória e as exporta para um xlsx por execução."""

    linhas: list[dict] = field(default_factory=list)

    def registrar(self, *, login_professor: str = "", persona_id: str = "", fase: str = "",
                  acao: str = "", detalhe: str = "", status: str = "") -> None:
        """Adiciona uma linha de log com o timestamp atual."""
        self.linhas.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "login_professor": login_professor,
            "persona_id": persona_id,
            "fase": fase,
            "acao": acao,
            "detalhe": detalhe,
            "status": status,
        })

    def registrar_erro(self, excecao: Exception, *, login_professor: str = "",
                       persona_id: str = "", fase: str = "") -> None:
        """Atalho para registrar uma linha de erro com a mensagem truncada."""
        self.registrar(login_professor=login_professor, persona_id=persona_id, fase=fase,
                       acao="erro", detalhe=resumir_erro(excecao), status="erro")

    def exportar(self, dir_logs) -> Path:
        """Escreve todas as linhas em logs/atribuicao_AAAAMMDD_HHMM.xlsx; retorna o caminho."""
        dir_logs = Path(dir_logs)
        dir_logs.mkdir(parents=True, exist_ok=True)
        caminho = dir_logs / f"atribuicao_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

        workbook = Workbook()
        planilha = workbook.active
        planilha.title = "atribuicao"
        planilha.append(COLUNAS_LOG)
        for linha in self.linhas:
            planilha.append([linha.get(coluna, "") for coluna in COLUNAS_LOG])
        workbook.save(caminho)
        return caminho
