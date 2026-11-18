"""Tempo do trabalho na máquina: estimativa de cada linha do G-code e previsão do restante corrigida pelo tempo real.

A conta (comprimento ÷ velocidade) não sabe das acelerações: na máquina tudo demora mais. Como o LaserGRBL, a
previsão compara o tempo real com o estimado do que já foi feito e aplica a mesma proporção ao que falta.
"""
import math
import re

_PALAVRA = re.compile(r"([GXYF])\s*(-?\d+(?:\.\d*)?|-?\.\d+)")
_CAMADA = re.compile(r";\s*Camada\s+(C\d\d)\s*\((.*)\)\s*:")


def estimar(linhas, rapido=6000.0):
    """Tempo acumulado (s) ao FIM de cada linha: G0 na velocidade rápida, G1/G2/G3 no F atual (arco pela corda)."""
    x = y = 0.0
    f, modo, t, out = 1000.0, 1, 0.0, []
    for ln in linhas:
        nx, ny = x, y
        for k, v in _PALAVRA.findall(ln.upper()):
            v = float(v)
            if k == "G" and v in (0, 1, 2, 3):
                modo = int(v)
            elif k == "X":
                nx = v
            elif k == "Y":
                ny = v
            elif k == "F" and v > 0:
                f = v
        d = math.hypot(nx - x, ny - y)
        if d:
            t += d / ((rapido if modo == 0 else f) / 60)
        x, y = nx, ny
        out.append(t)
    return out


_PALAVRA_S = re.compile(r"([GXYS])\s*(-?\d+(?:\.\d*)?|-?\.\d+)")


def trechos_com_laser(linhas):
    """Para cada linha: ((x0, y0), (x1, y1)) se ela anda COM laser (G1/G2/G3 e S > 0), senão None (coordenadas do
    trabalho). A tela de corte pinta de verde os trechos das linhas que a máquina já fez."""
    x = y = 0.0
    modo, s, out = 1, 0.0, []
    for ln in linhas:
        nx, ny = x, y
        for k, v in _PALAVRA_S.findall(ln.upper()):
            v = float(v)
            if k == "G" and v in (0, 1, 2, 3):
                modo = int(v)
            elif k == "X":
                nx = v
            elif k == "Y":
                ny = v
            elif k == "S":
                s = v
        out.append(((x, y), (nx, ny)) if modo and s > 0 and (nx, ny) != (x, y) else None)
        x, y = nx, ny
    return out


def camadas(texto):
    """Camada ("C01 Contornos") de cada linha que vai para a máquina (as mesmas de Conexao.linhas_do_gcode)."""
    atual, out = "", []
    for ln in texto.splitlines():
        m = _CAMADA.search(ln)
        if m:
            atual = f"{m.group(1)} {m.group(2)}"
        if ln.split(";", 1)[0].strip():
            out.append(atual)
    return out


class Previsao:
    """Tempo restante: estimado do que falta × (tempo real ÷ estimado do que já foi feito)."""

    MIN_S = 20.0  # antes disso a proporção ainda oscila muito: usa a estimativa pura

    def __init__(self, acumulado):
        self.acumulado = acumulado
        self.total = acumulado[-1] if acumulado else 0.0

    def restante(self, linha_feita, decorrido):
        """(segundos que faltam, fator real/estimado). `linha_feita`: quantas linhas a máquina já executou."""
        if not self.acumulado:
            return 0.0, 1.0
        feito = self.acumulado[min(max(linha_feita, 1), len(self.acumulado)) - 1] if linha_feita > 0 else 0.0
        fator = 1.0
        if feito >= self.MIN_S and decorrido > 0:
            fator = min(max(decorrido / feito, 0.5), 5.0)
        return max(0.0, (self.total - feito) * fator), fator


def fmt(segundos):
    s = int(round(segundos))
    h, m = divmod(s // 60, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min {s % 60:02d} s"


if __name__ == "__main__":  # autoteste rápido
    cum = estimar(["G21", "G0 X60 Y0", "G1 X60 Y60 F600", "G1 X0 F1200"], rapido=3600)
    assert [round(v, 2) for v in cum] == [0.0, 1.0, 7.0, 10.0], cum
    p = Previsao(cum)
    assert p.restante(0, 0) == (10.0, 1.0)
    print("ok")
