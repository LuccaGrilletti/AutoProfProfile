"""Leitura completa do Gestor de Classes (GC).

Monta o mapa professor_id → [ClasseGC] com as matérias e professores de cada classe. Deve ser
chamado UMA única vez por execução; o resultado é reutilizado para todos os professores.

Entry de debug (valida paginação + coleta contra o portal, com o Chrome logado):
    python -m src.harvester          # harvest completo
    python -m src.harvester 5        # processa só as 5 primeiras classes (checagem rápida)
"""

import re
from dataclasses import dataclass, field

from . import config
from .matching import classe_bate
from .registro import resumir_erro

# --- Seletores (estruturais, estáveis) ---
SELETOR_TABELA_GC = "table.mat-table.cdk-table.mat-sort"
SELETOR_LINHA_GC = "tr.mat-row"
# aria-label localizado + classe estrutural do Material como fallback (independe de locale)
SELETOR_BOTAO_PROXIMA = "button[aria-label='Página seguinte'], button.mat-paginator-navigation-next"
SELETOR_ABA_PROFESSORES = "//button[contains(@class,'nav-link') and normalize-space()='Professores']"
SELETOR_CHIP_MATERIA = "mat-chip.mat-standard-chip"
SELETOR_LINHA_PROF = "tr.mat-row.cdk-row.example-element-row"
# linhas de professor OU a linha "sem dados" do Material — evita esperar o timeout em classe vazia
SELETOR_PROF_OU_VAZIO = f"{SELETOR_LINHA_PROF}, tr.mat-no-data-row"

TIMEOUT_TABELA_PROF = 12_000  # espera mais curta na aba Professores (classe pode estar vazia)


@dataclass
class ProfessorGC:
    id: str
    nome: str


@dataclass
class ClasseGC:
    id: str
    nome: str
    materias: set[str] = field(default_factory=set)
    professores: list[ProfessorGC] = field(default_factory=list)


# Retorno do harvester: professor_id → [ClasseGC]
MapaProfessorClasses = dict[str, list[ClasseGC]]


def harvest_gc(page, url_gc: str, url_classe_base: str,
               limite_classes: int | None = None,
               filtro_turmas: list | None = None) -> MapaProfessorClasses:
    """Lê as classes do GC e retorna o mapa professor_id → [ClasseGC].

    limite_classes: se informado, processa só as N primeiras classes (para validação rápida).
    filtro_turmas: lista de TurmaAlvo; se informada, abre só as classes cujo nome casa com algum
        alvo (mesmo predicado classe_bate usado depois no perfil — não perde nada que será usado).
    """
    classes = _listar_classes(page, url_gc)
    print(f"[harvester] {len(classes)} classe(s) listada(s) no Gestor de Classes.")
    if filtro_turmas:
        antes = len(classes)
        classes = [(cid, nome) for cid, nome in classes
                   if any(classe_bate(nome, alvo) for alvo in filtro_turmas)]
        print(f"[harvester] filtro de turmas: {len(classes)}/{antes} classe(s) relevante(s).")
    if limite_classes is not None:
        classes = classes[:limite_classes]
        print(f"[harvester] processando apenas {len(classes)} classe(s) (limite).")

    mapa: MapaProfessorClasses = {}
    for i, (classe_id, classe_nome) in enumerate(classes, start=1):
        try:
            classe = _coletar_classe(page, url_classe_base, classe_id, classe_nome)
        except Exception as exc:
            # falha em uma classe não aborta o harvest — loga e segue
            print(f"[harvester] ERRO na classe {classe_id} ({classe_nome}): "
                  f"{resumir_erro(exc)} — pulando.")
            continue
        for prof in classe.professores:
            _acumular(mapa, prof.id, classe)
        if i % 25 == 0:
            print(f"[harvester] {i}/{len(classes)} classes processadas...")

    print(f"[harvester] mapa final: {len(mapa)} professor(es).")
    return mapa


# --- Passo 1: listar todas as classes (paginado) ---

def _listar_classes(page, url_gc: str) -> list[tuple[str, str]]:
    """Percorre todas as páginas da tabela do GC e retorna [(id_classe, nome_classe)]."""
    page.goto(url_gc, timeout=config.TIMEOUT_NAVEGACAO)
    page.wait_for_selector(SELETOR_TABELA_GC, timeout=config.TIMEOUT_ELEMENTO)

    total = _total_paginador(page)
    if total is not None:
        print(f"[harvester] paginador indica {total} classe(s).")

    classes: dict[str, str] = {}  # id → nome (dedupe preservando ordem)
    pagina = 1
    while True:
        page.wait_for_selector(SELETOR_LINHA_GC, timeout=config.TIMEOUT_ELEMENTO)
        for cid, nome in _ler_linhas_listagem(page):
            classes.setdefault(cid, nome)
        if not _proxima_pagina(page):
            break
        pagina += 1
        if pagina > 1000:  # trava de segurança contra loop infinito
            print("[harvester] limite de páginas atingido; interrompendo paginação.")
            break
    return list(classes.items())


def _ler_linhas_listagem(page) -> list[tuple[str, str]]:
    resultado = []
    for linha in page.query_selector_all(SELETOR_LINHA_GC):
        id_cell = linha.query_selector("td.cdk-column-geClaseId")
        if id_cell is None:
            continue
        cid = id_cell.inner_text().strip()
        nome_cell = linha.query_selector("td.cdk-column-geClase")
        nome = nome_cell.inner_text().strip() if nome_cell else ""
        if cid:
            resultado.append((cid, nome))
    return resultado


def _total_paginador(page) -> int | None:
    """Extrai o total de itens do texto do paginador (ex.: '1 - 10 de 468' → 468)."""
    try:
        texto = page.inner_text("mat-paginator")
    except Exception:
        return None
    match = re.search(r"de\s+(\d+)", texto)
    return int(match.group(1)) if match else None


def _id_primeira_linha(page) -> str:
    cell = page.query_selector(f"{SELETOR_TABELA_GC} {SELETOR_LINHA_GC} td.cdk-column-geClaseId")
    return cell.inner_text().strip() if cell else ""


def _proxima_pagina(page) -> bool:
    """Avança para a próxima página; False quando o botão está desabilitado/ausente.

    Após clicar, espera a tabela re-renderizar (SPA): a 1ª linha precisa mudar antes de relermos.
    """
    botao = page.query_selector(SELETOR_BOTAO_PROXIMA)
    if botao is None:
        return False
    if botao.is_disabled() or botao.get_attribute("aria-disabled") == "true":
        return False

    anterior = _id_primeira_linha(page)
    botao.click()
    try:
        page.wait_for_function(
            """(anterior) => {
                const c = document.querySelector(
                    'table.mat-table.cdk-table.mat-sort tr.mat-row td.cdk-column-geClaseId');
                return c && c.textContent.trim() !== anterior;
            }""",
            arg=anterior,
            timeout=config.TIMEOUT_ELEMENTO,
        )
    except Exception:
        return False  # 1ª linha não mudou — provável fim da paginação
    return True


# --- Passo 2: abrir cada classe e coletar matérias + professores ---

def _coletar_classe(page, url_classe_base: str, classe_id: str, classe_nome: str) -> ClasseGC:
    page.goto(f"{url_classe_base}{classe_id}", timeout=config.TIMEOUT_NAVEGACAO)
    # a presença da aba Professores indica que a página da classe carregou
    page.wait_for_selector(SELETOR_ABA_PROFESSORES, timeout=config.TIMEOUT_ELEMENTO)
    materias = _coletar_materias(page)
    professores = _coletar_professores(page)
    return ClasseGC(id=classe_id, nome=classe_nome, materias=materias, professores=professores)


def _coletar_materias(page) -> set[str]:
    materias = set()
    for chip in page.query_selector_all(SELETOR_CHIP_MATERIA):
        # O nome está no primeiro text node — ignora o ícone "close" do mat-chip-remove
        texto = chip.evaluate("""el => {
            return Array.from(el.childNodes)
                .filter(n => n.nodeType === Node.TEXT_NODE)
                .map(n => n.textContent.trim())
                .filter(t => t.length > 0)
                .join('');
        }""")
        if texto:
            materias.add(texto)
    return materias


def _coletar_professores(page) -> list[ProfessorGC]:
    """Abre a aba Professores e lê a tabela; lista vazia se a classe não tiver professores."""
    page.wait_for_selector(SELETOR_ABA_PROFESSORES, timeout=config.TIMEOUT_ELEMENTO)
    page.click(SELETOR_ABA_PROFESSORES)
    page.wait_for_timeout(2000)  # aguarda Angular renderizar conteúdo da aba
    
    # Imprime só a parte relevante do DOM após a aba carregar
    conteudo = page.evaluate("""() => {
        const el = document.querySelector('app-lista-participantes') 
                || document.querySelector('.tab-pane.active')
                || document.querySelector('router-outlet + *');
        return el ? el.innerHTML.substring(0, 2000) : 'componente não encontrado';
    }""")
    print(f"[debug] conteúdo aba Professores: {conteudo[:2000]}")
    try:
        page.wait_for_selector(SELETOR_PROF_OU_VAZIO, timeout=TIMEOUT_TABELA_PROF)
    except Exception:
        print("[debug] timeout esperando linhas de professor")
        return []

    linhas = page.query_selector_all(SELETOR_LINHA_PROF)
    print(f"[debug] linhas de professor encontradas: {len(linhas)}")

    professores = []
    for linha in page.query_selector_all(SELETOR_LINHA_PROF):
        id_cell = linha.query_selector("td.cdk-column-personaId")
        if id_cell is None:
            continue
        prof_id = id_cell.inner_text().strip()
        nome_cell = linha.query_selector("td.cdk-column-nombre")
        prof_nome = nome_cell.inner_text().strip() if nome_cell else ""
        if prof_id:
            professores.append(ProfessorGC(id=prof_id, nome=prof_nome))
    return professores


# --- Acumulação no mapa ---

def _acumular(mapa: MapaProfessorClasses, professor_id: str, classe: ClasseGC) -> None:
    """Adiciona a classe ao professor; se a classe já existe (mesmo id), une as matérias."""
    classes = mapa.setdefault(professor_id, [])
    for existente in classes:
        if existente.id == classe.id:
            existente.materias |= classe.materias
            return
    classes.append(classe)


# --- Entry de debug ---

def _debug(limite: int | None = None) -> None:
    from .sessao import obter_sessao

    pw = None
    try:
        pw, _browser, page = obter_sessao(config.AUTH_MODE, config.CDP_URL, config.URL_PEGASUS)
        mapa = harvest_gc(page, config.URL_GC, config.URL_CLASSE_BASE, limite_classes=limite)
    finally:
        if pw is not None:
            pw.stop()  # modo manual: NÃO fecha o Chrome do usuário

    classes_unicas = {c.id for classes in mapa.values() for c in classes}
    print("\n=== RESUMO HARVEST ===")
    print(f"professores únicos       : {len(mapa)}")
    print(f"classes únicas no mapa    : {len(classes_unicas)}")
    for pid, classes in list(mapa.items())[:3]:
        print(f"\nprofessor_id={pid} — {len(classes)} classe(s):")
        for classe in classes[:5]:
            print(f"   [{classe.id}] {classe.nome} | matérias: {sorted(classe.materias)}")


if __name__ == "__main__":
    import sys

    _limite = int(sys.argv[1]) if len(sys.argv) > 1 else None
    _debug(_limite)
