"""Teste de força da gravação de código QR em MDF 3 mm: 3 plaquinhas com o mesmo QR, cada uma numa potência.

Cada plaquinha (40 × 48 mm) leva o QR de 30 mm (margem livre de 5 mm, > 4 módulos) e a potência escrita embaixo.
As gravações (preenchimento, 3000 mm/min) saem antes; o contorno corta por último com o padrão de MDF 3 mm.

Executar:  python tools/projetos/teste_qrcode.py <saida.rbl>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QRectF  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import materiais as mt  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack import qrcode_rb as qr  # noqa: E402
from redblack import texto as tx  # noqa: E402

URL = "https://explorarlocais.com.br/"
POTENCIAS = (("C03", 20.0), ("C04", 30.0), ("C05", 40.0))
VELOCIDADE = 3000.0
LADO, MARGEM, PLACA_W, PLACA_H, ESPACO = 30.0, 5.0, 40.0, 48.0, 5.0


def camadas():
    grav = [cm.alterar(cm.Camada(lid, f"QR {p:.0f} % (gravação {i + 1}º)"), modo="preenchimento",
                       velocidade_mm_min=VELOCIDADE, potencia_max=p, potencia_min=0.0, passadas=1, intervalo_mm=0.1)
            for i, (lid, p) in enumerate(POTENCIAS)]
    return grav + [cm.alterar(cm.Camada("C01", "MDF 3: contorno das plaquinhas (por último)"), **mt.corte_mdf(3))]


def gerar(saida):
    snaps = []
    for i, (lid, p) in enumerate(POTENCIAS):
        x0, y0 = ESPACO + i * (PLACA_W + ESPACO), ESPACO
        q = qr.caminho(URL, LADO)
        q.translate(x0 + MARGEM, y0 + MARGEM)
        snaps.append(ob.Shape(q, f"QR {p:.0f} %", lid, cm.cor(lid)).snapshot())
        t = tx.build_path(tx.TextoParams(f"{p:.0f} %", "Arial", 5.0, negrito=True, alinhamento="centro"))
        b = t.boundingRect()
        t.translate(x0 + PLACA_W / 2 - b.center().x(), y0 + MARGEM + LADO + 6.5 - b.center().y())
        snaps.append(ob.Shape(t, f"Texto {p:.0f} %", lid, cm.cor(lid)).snapshot())
        snaps.append(ob.Shape(fm.rect_path(QRectF(x0, y0, PLACA_W, PLACA_H)), f"Plaquinha {p:.0f} %", "C01",
                              cm.cor("C01")).snapshot())
    pj.save(saida, snaps, camadas(),
            notas=f"Teste de força do QR ({URL}) em MDF 3 mm: C03 20 %, C04 30 %, C05 40 %, todas a "
                  f"{VELOCIDADE:.0f} mm/min, preenchimento, intervalo 0,1 mm, 1 passada.\n"
                  "C01 corta as plaquinhas por último (650 mm/min, 85 %, 2 passadas).\n"
                  "Leia cada uma com o celular e fique com a mais fraca que lê fácil e sem queimar as bordas.")
    return saida


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1]))
