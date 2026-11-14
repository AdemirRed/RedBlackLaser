"""Gabarito: grade de células na mesa para produzir várias peças iguais de uma vez.

Coordenadas de documento (mm, origem no topo esquerdo, Y para baixo). Células em ordem de leitura:
da esquerda para a direita, de cima para baixo; a peça k usa a linha (atual + k) da planilha.
O gabarito é só guia na tela: não vai para o G-code.
"""
import math
from dataclasses import asdict, dataclass, fields

MAX_CELULAS_LADO = 50


@dataclass(frozen=True)
class Gabarito:
    colunas: int = 3
    linhas: int = 2
    largura_mm: float = 60.0      # tamanho de cada célula
    altura_mm: float = 40.0
    espaco_x_mm: float = 5.0      # vão entre células
    espaco_y_mm: float = 5.0
    x_mm: float = 10.0            # canto superior esquerdo da 1ª célula (documento)
    y_mm: float = 10.0
    giro_graus: float = 0.0       # giro de cada peça dentro da célula (positivo = horário)

    @property
    def total(self) -> int:
        return self.colunas * self.linhas

    def celulas(self):
        """[(x, y, largura, altura)] em ordem de leitura."""
        return [(self.x_mm + c * (self.largura_mm + self.espaco_x_mm),
                 self.y_mm + r * (self.altura_mm + self.espaco_y_mm), self.largura_mm, self.altura_mm)
                for r in range(self.linhas) for c in range(self.colunas)]

    def limites(self):
        """(x0, y0, x1, y1) da grade inteira."""
        w = self.colunas * self.largura_mm + (self.colunas - 1) * self.espaco_x_mm
        h = self.linhas * self.altura_mm + (self.linhas - 1) * self.espaco_y_mm
        return self.x_mm, self.y_mm, self.x_mm + w, self.y_mm + h


def erros(gb: Gabarito, mesa_w: float, mesa_h: float) -> list:
    out = []
    for n in ("colunas", "linhas"):
        v = getattr(gb, n)
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= MAX_CELULAS_LADO:
            out.append(f"{n} deve ser inteiro de 1 a {MAX_CELULAS_LADO}")
    for n in ("largura_mm", "altura_mm", "espaco_x_mm", "espaco_y_mm", "x_mm", "y_mm", "giro_graus"):
        v = getattr(gb, n)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            out.append(f"{n} inválido")
    if out:
        return out
    if gb.largura_mm <= 0 or gb.altura_mm <= 0:
        out.append("célula precisa de largura e altura maiores que zero")
    if not -360 <= gb.giro_graus <= 360:
        out.append("giro deve ficar entre -360° e 360°")
    if gb.espaco_x_mm < 0 or gb.espaco_y_mm < 0:
        out.append("vão não pode ser negativo")
    x0, y0, x1, y1 = gb.limites()
    if x0 < -1e-6 or y0 < -1e-6 or x1 > mesa_w + 1e-6 or y1 > mesa_h + 1e-6:
        out.append(f"a grade ({x1 - x0:.1f} × {y1 - y0:.1f} mm) sai da mesa de {mesa_w:g} × {mesa_h:g} mm"
                   .replace(".", ","))
    return out


def caixa_girada(w: float, h: float, graus: float):
    """Largura e altura da caixa de um retângulo w × h depois de girado."""
    a = math.radians(graus)
    c, s_ = abs(math.cos(a)), abs(math.sin(a))
    return w * c + h * s_, w * s_ + h * c


def para_dict(gb: Gabarito) -> dict:
    return asdict(gb)


def de_dict(d) -> Gabarito:
    """Lê dados não confiáveis (projeto ou configurações). ValueError se inválido."""
    nomes = {f.name for f in fields(Gabarito)}
    if not isinstance(d, dict) or set(d) not in (nomes, nomes - {"giro_graus"}):  # giro opcional (v7 antigo)
        raise ValueError("campos do gabarito ausentes ou desconhecidos")
    conv = {}
    for f in fields(Gabarito):
        if f.name not in d:
            continue
        v = d[f.name]
        if f.type == "int" or f.type is int:
            if isinstance(v, bool) or not isinstance(v, int):
                raise ValueError(f"{f.name} deve ser inteiro")
        elif isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{f.name} deve ser número")
        conv[f.name] = v if f.name in ("colunas", "linhas") else float(v)
    gb = Gabarito(**conv)
    e = erros(gb, math.inf, math.inf)  # a mesa é conferida por quem usa
    if e:
        raise ValueError("; ".join(e))
    return gb
