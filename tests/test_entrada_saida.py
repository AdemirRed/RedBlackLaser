"""Entrada/saída do corte (lead-in/out): sempre do lado da sobra, também em furos; não vale com guias."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402

app = QApplication.instance() or QApplication([])

EXT = [(100, 100), (150, 100), (150, 150), (100, 150), (100, 100)]  # peça 50 × 50
FURO = [(120, 120), (130, 120), (130, 130), (120, 130), (120, 120)]


def dentro(p, poly):
    return pc._dentro(p, poly)


class EntradaSaidaTest(unittest.TestCase):
    def test_externo_entra_por_fora(self):
        r = pc.com_entrada_saida(EXT, [EXT, FURO], 3, 2)
        self.assertEqual(len(r), len(EXT) + 2)
        self.assertEqual(r[1:-1], EXT)
        self.assertFalse(dentro(r[0], EXT))  # começa fora da peça
        self.assertAlmostEqual(pc._dist(r[0], EXT[0]), 3)
        self.assertFalse(dentro(r[-1], EXT))
        self.assertAlmostEqual(pc._dist(r[-1], EXT[-1]), 2)

    def test_furo_entra_por_dentro_do_furo(self):
        r = pc.com_entrada_saida(FURO, [EXT, FURO], 3, 3)
        self.assertTrue(dentro(r[0], FURO))  # a sobra do furo é o miolo
        self.assertTrue(dentro(r[-1], FURO))

    def test_aberto_ou_zero_nao_muda(self):
        aberto = [(0, 0), (10, 0), (10, 10)]
        self.assertEqual(pc.com_entrada_saida(aberto, [aberto], 3, 3), aberto)
        self.assertEqual(pc.com_entrada_saida(EXT, [EXT], 0, 0), EXT)

    def test_fora_da_mesa_nao_poe(self):
        canto = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]  # encostado no canto da mesa
        r = pc.com_entrada_saida(canto, [canto], 3, 0)
        self.assertTrue(all(0 <= x and 0 <= y for x, y in r))

    def test_no_percurso_e_com_guias(self):
        p = QPainterPath()
        p.addRect(QRectF(100, 100, 50, 50))
        snap = ob.Shape(p, "q", "C01", cm.cor("C01")).snapshot()
        lay = cm.alterar(cm.nova("C01"), entrada_mm=4, saida_corte_mm=4)
        cortes = [t for t in pc.gerar([snap], [lay]).trechos if t.tipo == "corte"]
        self.assertEqual(len(cortes), 1)
        self.assertAlmostEqual(cortes[0].comprimento, 200 + 8, places=6)
        com_guias = cm.alterar(lay, guias_qtd=2, guias_mm=1)
        total = sum(t.comprimento for t in pc.gerar([snap], [com_guias]).trechos if t.tipo == "corte")
        self.assertAlmostEqual(total, 198, places=6)  # guias abrem o contorno: sem entrada/saída

    def test_projeto_antigo_abre_sem(self):
        from dataclasses import asdict
        from redblack import projeto as pj
        d = asdict(cm.nova("C01"))
        for k in ("entrada_mm", "saida_corte_mm"):
            del d[k]
        c, = pj.layers_from_dict({"camadas": [d]})
        self.assertEqual((c.entrada_mm, c.saida_corte_mm), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
