"""Camadas e parâmetros de corte/gravação (Etapa 9).

Cada camada é identificada pela cor da paleta (C00…C29) e guarda parâmetros independentes.
A ordem da lista é a ordem de saída (de cima para baixo). "visivel" só afeta a tela; "saida"
decide se a camada vai para o laser (as duas são independentes, como na referência).

Velocidade em mm/min (unidade nativa do G-code GRBL). Valores padrão NÃO são validados para
nenhuma máquina/material: servem só de ponto de partida e precisam de teste (Etapa 18).
"""
import re
from dataclasses import dataclass, replace

PALETA = ["#101010", "#2f6bff", "#e0313b", "#1fa34a", "#d6a400", "#e8742a", "#1fb5c9", "#c23bd4",
          "#8a8f99", "#3d4fd0", "#b22a2a", "#2bd46a", "#a8a820", "#c96a20", "#3aa0ff", "#a03aff",
          # C16–C29 (paleta ampliada para 30 camadas)
          "#6e7480", "#7b86e0", "#e07a86", "#5ec27a", "#e8d36a", "#f0a868", "#6ed8e6", "#e08aec",
          "#4a4f5a", "#1f2f9a", "#7a1f1f", "#1f7a3a", "#7a6a10", "#7a3f10"]
IDS = [f"C{i:02d}" for i in range(len(PALETA))]
MODOS = ("linha", "preenchimento", "imagem")
MODOS_VETOR = ("linha", "preenchimento")
_ID = re.compile(r"^C\d\d$")

LIMITES = {"velocidade_mm_min": (1.0, 60000.0), "potencia_max": (0.0, 100.0), "potencia_min": (0.0, 100.0),
           "passadas": (1, 99), "intervalo_mm": (0.01, 5.0), "kerf_mm": (0.0, 2.0),
           "angulo_graus": (-360.0, 360.0), "angulo_inc_graus": (-360.0, 360.0), "sobrevarredura_mm": (0.0, 50.0),
           "guias_qtd": (0, 50), "guias_mm": (0.0, 20.0), "sobrecorte_mm": (0.0, 20.0),
           "limiar_pct": (0.0, 100.0), "brilho_pct": (-100.0, 100.0), "contraste_pct": (-100.0, 100.0),
           "gama": (0.1, 5.0), "meio_tom_cpi": (5.0, 300.0), "meio_tom_angulo": (-180.0, 180.0),
           "entrada_mm": (0.0, 20.0), "saida_corte_mm": (0.0, 20.0)}
MODOS_IMAGEM = ("limiar", "pontilhado", "jarvis", "stucki", "atkinson", "cinza", "meio_tom")


@dataclass(frozen=True)
class Camada:
    id: str
    nome: str
    modo: str = "linha"
    velocidade_mm_min: float = 1000.0
    potencia_max: float = 20.0
    potencia_min: float = 0.0
    passadas: int = 1
    intervalo_mm: float = 0.1
    saida: bool = True
    visivel: bool = True
    air: bool = False
    kerf_mm: float = 0.0  # largura medida do corte; no modo Linha os contornos são deslocados k/2 (ver percurso)
    # Preenchimento (ver percurso.hachura): ângulo das linhas (0 = horizontal, 90 = vertical), quanto o ângulo
    # muda a cada passada, ida e volta ou sempre no mesmo sentido, segunda varredura a +90° e quanto o laser
    # passa apagado além de cada linha (para acelerar/frear fora da peça).
    angulo_graus: float = 0.0
    angulo_inc_graus: float = 0.0
    bidirecional: bool = True
    hachura_cruzada: bool = False
    sobrevarredura_mm: float = 0.0
    # Linha: pontes que seguram a peça na chapa (contornos fechados ficam com N trechos sem corte).
    guias_qtd: int = 0
    guias_mm: float = 0.5
    sobrecorte_mm: float = 0.0     # Linha: contorno fechado segue além do ponto inicial (fecha bem o corte)
    # Linha: entrada/saída (lead-in/out) — o corte começa e termina numa reta perpendicular do lado da sobra,
    # para a marca do início não ficar na peça.
    entrada_mm: float = 0.0
    saida_corte_mm: float = 0.0
    # Subcamadas: passes extras sobre os mesmos objetos, depois da camada, cada um com os ajustes que mudam:
    # tupla de tuplas ((campo, valor), …) com campos de SUB_CAMPOS (ver expandir()).
    subcamadas: tuple = ()
    preencher_juntas: bool = False  # Preenchimento: uma varredura para todos os objetos da camada (menos idas)
    # Imagem (ver raster.py): como os tons viram laser; negativo inverte claro/escuro.
    modo_imagem: str = "pontilhado"
    limiar_pct: float = 50.0
    negativo: bool = False
    brilho_pct: float = 0.0     # ajuste da imagem antes de virar laser (só gravação)
    contraste_pct: float = 0.0
    gama: float = 1.0
    meio_tom_cpi: float = 50.0     # Meio-tom: células (pontos) por polegada e ângulo da grade de pontos
    meio_tom_angulo: float = 45.0

    @property
    def cor(self) -> str:
        return cor(self.id)


def cor(layer_id: str) -> str:
    return PALETA[IDS.index(layer_id)] if layer_id in IDS else "#c9ccd2"


def nova(layer_id: str, imagem=False) -> Camada:
    if layer_id not in IDS:
        raise ValueError(f"camada desconhecida: {layer_id}")
    return Camada(layer_id, layer_id, "imagem" if imagem else "linha")


SUB_CAMPOS = ("modo", "velocidade_mm_min", "potencia_max", "potencia_min", "passadas", "intervalo_mm",
              "angulo_graus", "bidirecional", "hachura_cruzada", "sobrevarredura_mm", "kerf_mm")
MAX_SUB = 10


def base_id(layer_id: str) -> str:
    """"C01.2" (subcamada virtual) -> "C01"."""
    return layer_id.split(".", 1)[0]


def sub_aplicada(c: Camada, sub) -> Camada:
    """A camada virtual de uma subcamada: herda tudo da camada e troca só os campos da subcamada."""
    return replace(c, subcamadas=(), **dict(sub))


def expandir(camadas) -> list:
    """Camadas na ordem de saída com as subcamadas logo depois da sua camada, como camadas virtuais
    ("C01.1", "C01.2"…) que atuam sobre os objetos da camada. Idempotente."""
    out = []
    for c in camadas:
        out.append(replace(c, subcamadas=()) if c.subcamadas else c)
        for k, sub in enumerate(c.subcamadas, 1):
            out.append(replace(sub_aplicada(c, sub), id=f"{c.id}.{k}", nome=f"{c.nome} · sub {k}"))
    return out


def validar(c: Camada) -> list:
    """Lista de problemas (vazia = válida)."""
    erros = []
    if not _ID.match(c.id) or c.id not in IDS:
        erros.append(f"identificador inválido: {c.id}")
    if c.modo not in MODOS:
        erros.append(f"modo inválido: {c.modo}")
    for campo, (lo, hi) in LIMITES.items():
        v = getattr(c, campo)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            erros.append(f"{campo} fora de {lo}–{hi}: {v}")
    if isinstance(c.passadas, float):
        erros.append("passadas deve ser inteiro")
    if isinstance(c.guias_qtd, float):
        erros.append("guias_qtd deve ser inteiro")
    if not erros and c.potencia_min > c.potencia_max:
        erros.append("potência mínima maior que a máxima")
    if c.modo_imagem not in MODOS_IMAGEM:
        erros.append(f"modo de imagem inválido: {c.modo_imagem}")
    if not isinstance(c.subcamadas, tuple) or len(c.subcamadas) > MAX_SUB:
        erros.append(f"subcamadas devem ser no máximo {MAX_SUB}")
    else:
        for k, sub in enumerate(c.subcamadas, 1):
            if c.modo == "imagem":
                erros.append("camada de imagem não tem subcamadas")
                break
            if not isinstance(sub, tuple) or not all(isinstance(p, tuple) and len(p) == 2 for p in sub) \
                    or not {p[0] for p in sub} <= set(SUB_CAMPOS):
                erros.append(f"subcamada {k} inválida")
                continue
            v = sub_aplicada(c, sub)
            if v.modo not in MODOS_VETOR:
                erros.append(f"subcamada {k}: modo deve ser linha ou preenchimento")
            erros += [f"subcamada {k}: {e}" for e in validar(v)]
    for b in ("saida", "visivel", "air", "bidirecional", "hachura_cruzada", "preencher_juntas", "negativo"):
        if not isinstance(getattr(c, b), bool):
            erros.append(f"{b} deve ser verdadeiro/falso")
    return erros


def alterar(c: Camada, **campos) -> Camada:
    """Cópia com campos alterados; recusa valores inválidos (o original fica intacto)."""
    novo = replace(c, **campos)
    erros = validar(novo)
    if erros:
        raise ValueError("; ".join(erros))
    return novo
