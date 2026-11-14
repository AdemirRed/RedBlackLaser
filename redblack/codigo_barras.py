"""Código de barras EAN-13 (etiquetas de produto), próprio. 12 dígitos + dígito verificador calculado.

`barras(numero)` → (sequência de 95 módulos 0/1, número completo de 13 dígitos);
`caminho(numero, largura_mm, altura_mm)` → QPainterPath com as barras (retângulos), para gravar em Preenchimento.
Deixe margem clara de 11 módulos à esquerda e 7 à direita para leitura.
"""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

_L = ("0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011")
_R = tuple("".join("1" if b == "0" else "0" for b in c) for c in _L)
_G = tuple(c[::-1] for c in _R)
_PARIDADE = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")


class NumeroInvalido(ValueError):
    pass


def digito_verificador(doze: str) -> int:
    soma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(doze))
    return (10 - soma % 10) % 10


def barras(numero: str):
    n = "".join(ch for ch in numero if not ch.isspace())
    if not n.isdigit() or len(n) not in (12, 13):
        raise NumeroInvalido("EAN-13: digite 12 dígitos (o 13º é calculado) ou os 13.")
    dv = digito_verificador(n[:12])
    if len(n) == 13 and int(n[12]) != dv:
        raise NumeroInvalido(f"EAN-13: dígito verificador errado (o correto é {dv}).")
    n = n[:12] + str(dv)
    par = _PARIDADE[int(n[0])]
    bits = "101"
    for d, p in zip(n[1:7], par):
        bits += (_L if p == "L" else _G)[int(d)]
    bits += "01010"
    for d in n[7:]:
        bits += _R[int(d)]
    bits += "101"
    return bits, n


def caminho(numero: str, largura_mm: float, altura_mm: float) -> QPainterPath:
    bits, _ = barras(numero)
    m = largura_mm / len(bits)
    p = QPainterPath()
    i = 0
    while i < len(bits):
        if bits[i] == "1":
            j = i
            while j < len(bits) and bits[j] == "1":
                j += 1
            p.addRect(QRectF(i * m, 0, (j - i) * m, altura_mm))
            i = j
        else:
            i += 1
    return p
