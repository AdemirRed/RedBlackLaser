"""Maria Olivia: 18 peças, aplicações em 1:1 alisadas, rebaixo = peça + folga, coração na coroa e miolo na flor."""
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
PDF = r"F:\Downloads\Maria_Olivia_Projeto_MDF3_Rebaixos.pdf"


@unittest.skipUnless(os.path.exists(PDF), "PDF da Maria Olivia não está neste PC")
class MariaOliviaTest(unittest.TestCase):
    def test_pecas_rebaixos_e_chapas(self):
        import maria_olivia as mo
        import presepio as pr
        pecas = mo.ler(PDF)
        self.assertEqual(len(pecas), 18)
        for k, (w, h) in mo.TAMANHOS.items():  # tamanho 1:1 da tabela (alisado: décimos)
            r = pecas[k]["cont"].boundingRect()
            self.assertAlmostEqual(r.width(), w, delta=0.6, msg=k)
        self.assertTrue(all(min(p.boundingRect().width(), p.boundingRect().height()) >= 1.0
                            for v in pecas.values() for p, t in v["partes"] if t == "furo"))  # sem lascas
        # rebaixo do coração na coroa: área do coração + folga por lado (maior que a peça, nunca menor)
        reb = next(p for p, t in pecas["K01"]["partes"] if t == "rebaixo")
        self.assertGreater(pr._area(reb), pr._area(pecas["H01"]["cont"]))
        self.assertTrue(any(t == "cheio" for _, t in pecas["C01"]["partes"]))  # mechas gravadas no cabelo
        _s, _ap, chapas = mo.gerar(PDF, os.path.join(tempfile.mkdtemp(), "m.rbl"))
        self.assertEqual(len(chapas), 2)


if __name__ == "__main__":
    unittest.main()
