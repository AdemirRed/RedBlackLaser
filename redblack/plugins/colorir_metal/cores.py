"""Colorir metal (inox/titânio) com laser: a cor da camada de óxido depende da potência e do intervalo entre linhas
(e da velocidade). O fluxo é o mesmo dos anúncios de laser de diodo:

1. grade de teste: quadrados com potência × intervalo diferentes, gravados na mesma placa;
2. foto da placa gravada -> cor de cada quadrado (paleta do SEU material/máquina);
3. colorir: escolher uma cor da paleta aplica potência, intervalo e velocidade numa camada de Preenchimento.

A paleta "referência" vem da foto de um anúncio (20 W, 4000 mm/min, inox): serve só de ponto de partida, as cores
reais mudam com o metal, a limpeza, o foco e a máquina — grave a grade e leia a SUA paleta.
"""
import dataclasses
import json
import math
import os

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainterPath

from ... import camadas as cm
from ... import formas as fm
from ... import objetos as ob
from ... import texto as tx

GRADE_PADRAO = dict(pot_ini=25.0, pot_fim=55.0, pot_passo=5.0,
                    intervalos=(0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10),
                    velocidade=4000.0, passadas=1, lado=8.0, espaco=3.0, rotulos=True,
                    pot_rotulo=60.0, vel_rotulo=1500.0)

# Cores lidas da foto do anúncio (linhas = potência 25..55 %, colunas = intervalo 0,01..0,10 mm; 4000 mm/min)
_REF = [["#feedfe", "#fdcc7f", "#efc288", "#d8b97f", "#dbbd7b", "#d8c499", "#cdbf86", "#d2bf9b", "#c2b998", "#bab495"],
        ["#fefeff", "#baeafe", "#6da2fc", "#585fac", "#694357", "#71465d", "#7e5258", "#9a7046", "#714c1e", "#91713e"],
        ["#fdfef1", "#fefefe", "#c4e3ea", "#afcfe4", "#6f91b7", "#718fa9", "#6188a5", "#687c96", "#6f7595", "#6a6172"],
        ["#dbcec2", "#d4aba9", "#f2e2be", "#cbcab0", "#bdbfb2", "#b2b6b4", "#9fa393", "#979b8a", "#969f9c", "#889795"],
        ["#a89d8c", "#9fa9aa", "#cdb0be", "#e7b998", "#d5c08e", "#b3b09e", "#9fa193", "#a0a297", "#8e9591", "#8e9b9a"],
        ["#a79480", "#95856e", "#847b63", "#87735b", "#927958", "#9a8d6a", "#9e9a74", "#95937a", "#9c9f89", "#abaf9c"],
        ["#8b7966", "#957f5a", "#8a7b55", "#7a6b52", "#7b6742", "#88835f", "#857d59", "#949271", "#9a9778", "#aaaf9c"]]


@dataclasses.dataclass(frozen=True)
class Cor:
    cor: str            # #rrggbb lida da placa
    potencia: float     # %
    intervalo: float    # mm
    velocidade: float   # mm/min
    passadas: int = 1

    @property
    def rotulo(self):
        return (f"{self.potencia:g} % · {self.intervalo:.2f} mm · {self.velocidade:g} mm/min"
                + (f" · {self.passadas}×" if self.passadas > 1 else "")).replace(".", ",")


def potencias(cfg) -> list:
    out, p = [], cfg["pot_ini"]
    while p <= cfg["pot_fim"] + 1e-9 and len(out) < 30:
        out.append(round(p, 3))
        p += max(cfg["pot_passo"], 0.1)
    return out


def paleta_referencia(nome="Inox — referência do anúncio (20 W)") -> dict:
    cfg = GRADE_PADRAO
    cores = [Cor(_REF[i][j], p, iv, cfg["velocidade"]) for i, p in enumerate(potencias(cfg))
             for j, iv in enumerate(cfg["intervalos"])]
    return {"nome": nome, "referencia": True, "cores": cores}


# ---------- grade de teste ----------
def celulas(cfg) -> list:
    """[(linha, coluna, potência, intervalo, QRectF)] com a origem (0, 0) no canto da grade (fora os rótulos)."""
    margem_x = 14.0 if cfg["rotulos"] else 0.0
    out = []
    for i, p in enumerate(potencias(cfg)):
        for j, iv in enumerate(cfg["intervalos"]):
            x = margem_x + j * (cfg["lado"] + cfg["espaco"])
            y = i * (cfg["lado"] + cfg["espaco"])
            out.append((i, j, p, iv, QRectF(x, y, cfg["lado"], cfg["lado"])))
    return out


def tamanho_grade(cfg):
    cs = celulas(cfg)
    r = QRectF()
    for *_, q in cs:
        r = r.united(q)
    return r.right(), r.bottom() + (8.0 if cfg["rotulos"] else 0.0)


def _texto(s, x, y, altura=2.5):
    return QPainterPath(tx.build_path(tx.TextoParams(s, "Arial", altura))).translated(x, y)


def montar_grade(cfg, x0, y0):
    """(snapshots, camadas) da grade na mesa (canto em x0, y0). Cada quadrado tem a própria camada interna (T…):
    não ocupa as camadas do projeto."""
    snaps, camadas = [], []
    for k, (i, j, p, iv, r) in enumerate(celulas(cfg), 1):
        lid = f"T{k:03d}"
        camadas.append(cm.Camada(lid, f"{p:g}% {iv:g}mm", "preenchimento", velocidade_mm_min=cfg["velocidade"],
                                 potencia_max=p, potencia_min=0.0, passadas=int(cfg["passadas"]), intervalo_mm=iv,
                                 bidirecional=True))
        snaps.append(ob.Shape(fm.rect_path(r.translated(x0, y0)), f"{p:g}% {iv:g}", lid, "#2f6bff").snapshot())
    if cfg["rotulos"]:
        rot = QPainterPath()
        for i, p in enumerate(potencias(cfg)):
            rot.addPath(_texto(f"{p:g}", x0, y0 + i * (cfg["lado"] + cfg["espaco"]) + cfg["lado"] / 2 + 1.2))
        larg, alt = tamanho_grade(cfg)
        for j, iv in enumerate(cfg["intervalos"]):
            rot.addPath(_texto(f"{iv:g}".lstrip("0"), x0 + 14 + j * (cfg["lado"] + cfg["espaco"]), y0 + alt - 1.5,
                               2.2))
        camadas.append(cm.Camada("TROT", "Rótulos", "linha", velocidade_mm_min=cfg["vel_rotulo"],
                                 potencia_max=cfg["pot_rotulo"], potencia_min=0.0, passadas=1))
        snaps.append(ob.Shape(rot, "Rótulos", "TROT", "#000000").snapshot())
    return snaps, camadas


def gcode_grade(cfg, x0=5.0, y0=5.0, rapido=None):
    """G-code da grade de teste (usa o perfil de máquina atual)."""
    from ... import gcode as gc
    from ... import percurso as pc
    snaps, camadas = montar_grade(cfg, x0, y0)
    perc = pc.gerar(snaps, camadas, **({"rapido": rapido} if rapido else {}))
    return gc.gerar(perc, camadas), perc


# ---------- ler as cores da foto da placa ----------
def ler_foto(imagem: QImage, primeiro: QPointF, ultimo: QPointF, linhas: int, colunas: int, raio_frac=0.2):
    """Cor média de cada quadrado. `primeiro`/`ultimo` = centro do quadrado do canto superior esquerdo e do
    inferior direito, em pixels da foto (foto de frente, sem inclinação)."""
    dx = (ultimo.x() - primeiro.x()) / max(colunas - 1, 1)
    dy = (ultimo.y() - primeiro.y()) / max(linhas - 1, 1)
    raio = max(1, int(min(abs(dx) or abs(dy), abs(dy) or abs(dx)) * raio_frac))
    img = imagem.convertToFormat(QImage.Format_RGB32)
    out = []
    for i in range(linhas):
        lin = []
        for j in range(colunas):
            cx, cy = round(primeiro.x() + j * dx), round(primeiro.y() + i * dy)
            r = g = b = n = 0
            for y in range(max(0, cy - raio), min(img.height(), cy + raio + 1), max(1, raio // 6)):
                for x in range(max(0, cx - raio), min(img.width(), cx + raio + 1), max(1, raio // 6)):
                    c = img.pixelColor(x, y)
                    r, g, b, n = r + c.red(), g + c.green(), b + c.blue(), n + 1
            lin.append(QColor(r // max(n, 1), g // max(n, 1), b // max(n, 1)).name())
        out.append(lin)
    return out


def paleta_da_foto(nome, cores_lidas, cfg) -> dict:
    ps = potencias(cfg)
    return {"nome": nome, "referencia": False,
            "cores": [Cor(cores_lidas[i][j], p, iv, cfg["velocidade"], int(cfg["passadas"]))
                      for i, p in enumerate(ps) for j, iv in enumerate(cfg["intervalos"])]}


# ---------- paletas salvas ----------
def carregar(arquivo) -> list:
    try:
        with open(arquivo, encoding="utf-8") as f:
            d = json.load(f)
        return [{"nome": p["nome"], "referencia": bool(p.get("referencia")),
                 "cores": [Cor(**c) for c in p["cores"]]} for p in d["paletas"]]
    except (OSError, ValueError, KeyError, TypeError):
        return [paleta_referencia()]


def salvar(arquivo, paletas):
    os.makedirs(os.path.dirname(arquivo), exist_ok=True)
    d = {"paletas": [{"nome": p["nome"], "referencia": p["referencia"],
                      "cores": [dataclasses.asdict(c) for c in p["cores"]]} for p in paletas]}
    tmp = arquivo + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, arquivo)


def mais_proxima(cores, alvo: str) -> Cor:
    """Cor da paleta mais parecida (distância RGB com pesos da percepção)."""
    a = QColor(alvo)

    def dist(c):
        b = QColor(c.cor)
        rm = (a.red() + b.red()) / 2
        dr, dg, db = a.red() - b.red(), a.green() - b.green(), a.blue() - b.blue()
        return math.sqrt((2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db)
    return min(cores, key=dist)


# ---------- aplicar no projeto ----------
def camada_livre(janela, cor: Cor):
    """Camada já configurada com esta cor, ou a primeira camada sem uso (devolve id ou None)."""
    nome = f"Cor {cor.cor} ({cor.rotulo})"
    existente = next((c for c in janela.layers if c.nome == nome), None)
    if existente:
        return existente.id
    usadas, _ = janela.used_layers()
    ocupadas = usadas | {c.id for c in janela.layers if c.nome.startswith("Cor #")}
    return next((lid for lid in cm.IDS[1:] if lid not in ocupadas), None)


def aplicar(janela, cor: Cor) -> str:
    """Passa as formas selecionadas para uma camada de Preenchimento com a potência/intervalo/velocidade da cor."""
    if not janela._sel():
        raise ValueError("Selecione as formas que vão receber a cor.")
    lid = camada_livre(janela, cor)
    if lid is None:
        raise ValueError("Todas as camadas estão em uso.")
    janela.assign_layer(lid)
    janela.set_layer_fields(lid, dict(nome=f"Cor {cor.cor} ({cor.rotulo})", modo="preenchimento",
                                      velocidade_mm_min=cor.velocidade, potencia_max=cor.potencia, potencia_min=0.0,
                                      passadas=cor.passadas, intervalo_mm=max(cor.intervalo, 0.01), saida=True),
                            f"Colorir {cor.cor}")
    return lid
