"""Princesas: 18 peças do PDF com as medidas do mapa, sem as lascas de 2 mm, em 3 chapas com 2 mm."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tools", "projetos"))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
PDF = r"F:\Downloads\Princesas_Contorno_Integrado_Sem_Pingo.pdf"
MEDIDAS = {"F1A": (353.9, 256.0), "F1B": (176, 244), "F2": (348, 244), "C1": (20, 244), "P1": (70, 190),
           "D1": (190.9, 246), "D3": (331, 66)}


@unittest.skipUnless(os.path.exists(PDF), "PDF das Princesas não está neste PC")
class PrincesasTest(unittest.TestCase):
    def test_pecas_e_chapas(self):
        import princesas as pz
        from redblack import projeto as pj
        pecas = pz.ler(PDF)
        self.assertEqual(len(pecas), 18)
        for k, (w, h) in MEDIDAS.items():
            r = pecas[k]["cont"].boundingRect()
            self.assertAlmostEqual(r.width(), w, delta=0.2, msg=k)
            self.assertAlmostEqual(r.height(), h, delta=0.2, msg=k)
        janelas = [p for p, t in pecas["F1A"]["partes"] if t == "furo"]
        self.assertEqual(len(janelas), 4)  # janela da foto, coração e 2 vazios do cabelo (sem as lascas)
        saida = os.path.join(tempfile.mkdtemp(), "p.rbl")
        _s, ap, chapas, dentro = pz.gerar(PDF, saida)
        self.assertEqual(len(chapas), 3)  # o PDF usava 4
        self.assertIn("P1", dentro)  # os pés aproveitam a janela da foto
        pj.load(saida)
        with open(saida, encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual({c["id"] for c in d["camadas"]}, {"C01", "C02", "C05", "C06"})
        self.assertTrue(all(c["potencia_max"] <= 85 for c in d["camadas"]))


if __name__ == "__main__":
    unittest.main()
