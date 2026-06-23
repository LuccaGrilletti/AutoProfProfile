"""Configuração do projeto: variáveis do .env, URLs derivadas e constantes de execução.

Fonte única de verdade — nenhum outro módulo lê variáveis de ambiente diretamente nem monta
URLs à mão. Importe sempre daqui.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# config.py vive em src/; a raiz do projeto (onde está o .env) é dois níveis acima.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- Identificadores do colégio / ano letivo ---
COLEGIO_ID = os.getenv("COLEGIO_ID", "29457").strip()
CICLO_ID = os.getenv("CICLO_ID", "1476").strip()      # ano letivo corrente — atualizar anualmente
NIVEL_ID = os.getenv("NIVEL_ID", "33").strip()        # 33 funciona mesmo quando o portal indica 32

# --- Endpoints ---
URL_PEGASUS = os.getenv(
    "URL_PEGASUS", "https://apps.uno-internacional.com/br/sumun/pegasus/dashboard"
).strip()
URL_BASE = os.getenv(
    "URL_BASE", "https://apps.uno-internacional.com/br/sumun/pegasus"
).strip().rstrip("/")
CDP_URL = os.getenv("CDP_URL", "http://localhost:9222").strip()

# --- Modo de autenticação ---
AUTH_MODE = os.getenv("AUTH_MODE", "manual").strip().lower()   # "manual" | "auto"

# --- Execução ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
RETRY_MAX = int(os.getenv("RETRY_MAX", "3"))

# --- URLs derivadas (montadas a partir das variáveis acima, nunca hardcoded) ---
_PREFIXO = f"{URL_BASE}/colegio/{COLEGIO_ID}/cicloEscolar/{CICLO_ID}"
URL_GC = f"{_PREFIXO}/gestor-clases"
URL_CENSO = f"{_PREFIXO}/censo/buscar/profesor"
URL_CLASSE_BASE = f"{_PREFIXO}/gestor-clases/editar?geClaseId="   # + classe_id
URL_PROFESSOR_BASE = f"{_PREFIXO}/censo/profesores/"             # + persona_id + ?nivelId=NIVEL_ID


def url_classe(classe_id: str) -> str:
    """URL de edição de uma classe do Gestor de Classes."""
    return f"{URL_CLASSE_BASE}{classe_id}"


def url_professor(persona_id: str) -> str:
    """URL do perfil de um professor no CENSO."""
    return f"{URL_PROFESSOR_BASE}{persona_id}?nivelId={NIVEL_ID}"


# --- Timeouts (ms) ---
TIMEOUT_ELEMENTO = 30_000
TIMEOUT_NAVEGACAO = 60_000

# --- Diretórios de runtime ---
DIR_DADOS = BASE_DIR / "dados"
DIR_LOGS = BASE_DIR / "logs"
CAMINHO_PLANILHA = DIR_DADOS / "input_professores.xlsx"
