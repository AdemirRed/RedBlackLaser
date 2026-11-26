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
        # rebaixo (assento) da silhueta D1 e da palavra D3 coladas por cima: peça + 0,1 mm por lado, dentro da base
        for b in ("F1A", "F1B", "C1"):
            self.assertTrue(any(t == "rebaixo" for _p, t in pecas[b]["partes"]), b)
        self.assertFalse(any(t == "rebaixo" for k in pecas if k not in ("F1A", "F1B", "C1") for _p, t in pecas[k]["partes"]))
        d1 = pz._na_montagem(pz.mo._area_util(pecas["D1"]["cont"], [p for p, t in pecas["D1"]["partes"] if t == "furo"]), "D1")
        reb = next(p for p, t in pecas["F1A"]["partes"] if t == "rebaixo")
        reb = pz._na_montagem(reb, "F1A")
        self.assertLess(d1.subtracted(reb).boundingRect().width() * d1.subtracted(reb).boundingRect().height(), 1.0)  # cobre D1
        base = pz._na_montagem(pecas["F1A"]["cont"], "F1A")
        fora = reb.subtracted(base)
        self.assertLess(fora.boundingRect().width() * fora.boundingRect().height() if not fora.isEmpty() else 0, 1.0)
        # o rebaixo não passa para a janela da foto (146 × 206)
        foto = pz._na_montagem(next(p for p, t in pecas["F1A"]["partes"] if t == "furo"
                                    and abs(p.boundingRect().width() - 146) < 0.5), "F1A")
        self.assertTrue(reb.intersected(foto).isEmpty() or reb.intersected(foto).boundingRect().width() < 0.05)
        saida = os.path.join(tempfile.mkdtemp(), "p.rbl")
        _s, ap, chapas, dentro = pz.gerar(PDF, saida)
        self.assertEqual(len(chapas), 3)  # o PDF usava 4
        self.assertIn("P1", dentro)  # os pés aproveitam a janela da foto
        pj.load(saida)
        with open(saida, encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual({c["id"] for c in d["camadas"]}, {"C10", "C01", "C02", "C05", "C06"})
        c10 = next(c for c in d["camadas"] if c["id"] == "C10")
        self.assertEqual((c10["velocidade_mm_min"], c10["potencia_max"], c10["passadas"]), (1500.0, 60.0, 1))
        self.assertTrue(all(c["velocidade_mm_min"] == 630.0 for c in d["camadas"] if c["id"] != "C10"))
        self.assertTrue(all(c["potencia_max"] <= 85 for c in d["camadas"]))


if __name__ == "__main__":
    unittest.main()
