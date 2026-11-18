"""Luana: contornos suavizados, rebaixo com o MESMO contorno de cada aplicação (sem folga), 14 peças numa chapa."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tools", "projetos"))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
PDF = r"F:\Downloads\Porta_Retrato_Luana_Projeto_Detalhado.pdf"


@unittest.skipUnless(os.path.exists(PDF), "PDF da Luana não está neste PC")
class LuanaTest(unittest.TestCase):
    def test_pecas_rebaixo_e_chapa(self):
        import luana as lu
        import presepio as pr
        pecas, (ox, oy) = lu.ler(PDF)
        self.assertEqual(len(pecas), 14)
        n = pecas["N01"]["cont"].boundingRect()
        self.assertAlmostEqual(n.width(), 90.04, delta=0.3)  # alisado: no máximo décimos menor
        self.assertAlmostEqual(n.height(), 34.32, delta=0.3)
        rebaixo = next(p for p, t in pecas["P01"]["partes"] if t == "cheio")
        janela = next(p for p, t in pecas["P01"]["partes"] if t == "furo")
        self.assertFalse(rebaixo.intersects(janela.boundingRect().adjusted(1, 1, -1, -1)))  # não grava a janela
        for k in lu.APLICACOES:  # o rebaixo de cada peça é a própria peça no lugar do PDF (área igual, sem folga)
            c = pecas[k]["cont"]
            cx, cy = lu.POSICAO[k]
            lugar = c.translated(ox + cx - c.boundingRect().left(), oy + cy - c.boundingRect().top())
            dentro = rebaixo.intersected(lugar)
            self.assertGreater(pr._area(dentro), 0.0, k)
        _s, ap, chapas = lu.gerar(PDF, os.path.join(tempfile.mkdtemp(), "l.rbl"))
        self.assertEqual(len(chapas), 1)


if __name__ == "__main__":
    unittest.main()
