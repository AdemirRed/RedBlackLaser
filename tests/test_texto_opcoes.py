"""Texto: Maiúsculas, Soldado e Distorcer (texto ao longo do caminho); salvos no projeto."""
import os
import sys
import unittest
from dataclasses import asdict, replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import projeto as pj  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack import texto_caminho as txc  # noqa: E402

app = QApplication.instance() or QApplication([])
BASE = tx.TextoParams("abc", "Arial", 10.0)


def subcaminhos(path):
    return len(path.toSubpathPolygons())


class TextoOpcoesTest(unittest.TestCase):
    def test_maiusculas_igual_a_digitar_maiusculo(self):
        a = tx.build_path(replace(BASE, maiusculas=True)).boundingRect()
        b = tx.build_path(replace(BASE, texto="ABC")).boundingRect()
        self.assertAlmostEqual(a.width(), b.width(), places=6)
        self.assertAlmostEqual(a.height(), b.height(), places=6)
        self.assertEqual(replace(BASE, maiusculas=True).texto, "abc")  # o digitado é mantido

    def test_soldado_funde_letras_que_se_tocam(self):
        p = replace(BASE, texto="WW", espacamento=1.0)
        solto, soldado = tx.build_path(p), tx.build_path(replace(p, soldado=True))
        # W de Arial se sobrepõe ao vizinho? Se não, compara ao menos que a área coberta é a mesma.
        self.assertLessEqual(subcaminhos(soldado), subcaminhos(solto))
        for pt in (QPointF(x, y) for x in range(0, 20) for y in range(-10, 1)):
            self.assertEqual(solto.contains(pt), soldado.contains(pt), pt)
        o = tx.build_path(replace(BASE, texto="O", soldado=True))
        c = o.boundingRect().center()
        self.assertFalse(o.contains(c))  # o furo do O continua furo

    def test_distorcer_curva_as_letras(self):
        circ = QPainterPath()
        circ.addEllipse(QRectF(-50, -50, 100, 100))
        p = replace(BASE, texto="HHHH", alinhamento="centro")
        rigido = txc.aplicar(p, circ, 25)
        curvo = txc.aplicar(replace(p, distorcer=True), circ, 25)
        self.assertFalse(curvo.isEmpty())
        r, c = rigido.boundingRect(), curvo.boundingRect()
        self.assertLess(abs(r.center().x() - c.center().x()), 3)  # mesmo lugar no caminho
        self.assertLess(abs(r.center().y() - c.center().y()), 3)
        self.assertNotEqual(subcaminhos(rigido), 0)
        # pontos do texto curvado ficam numa faixa em volta do círculo (altura da letra ~10 mm, de um dos lados)
        for poly in curvo.toSubpathPolygons():
            for q in poly:
                self.assertLess(abs((q.x() ** 2 + q.y() ** 2) ** 0.5 - 50), 12)

        def na_curva(path):  # pontos sobre o círculo (a base das letras)
            return sum(abs((q.x() ** 2 + q.y() ** 2) ** 0.5 - 50) < 0.01 for poly in path.toSubpathPolygons()
                       for q in poly)
        # curvado: toda a base do H fica sobre o círculo; rígido: a base é reta (corda), só toca no meio
        self.assertGreaterEqual(na_curva(curvo), 8)
        self.assertGreater(na_curva(curvo), na_curva(rigido))

    def test_projeto_guarda_e_le_e_aceita_versao_antiga(self):
        p = replace(BASE, maiusculas=True, soldado=True, distorcer=True)
        d = asdict(p)
        lido = pj._texto(d, "teste")
        self.assertEqual(lido, p)
        for k in ("maiusculas", "soldado", "distorcer"):
            del d[k]
        self.assertEqual(pj._texto(d, "teste"), BASE)  # projeto até a versão 16
        with self.assertRaises(pj.ProjetoInvalido):
            pj._texto({**asdict(BASE), "soldado": "sim"}, "teste")


if __name__ == "__main__":
    unittest.main()
