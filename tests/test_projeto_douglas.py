"""Cliente Douglas (PDF Carine V2): nome Carine do PDF pousado na borda com rebaixo, trio gravado, 3 chapas com 2 mm."""
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
PDF = r"F:\Downloads\Carine_V2_Projeto_Laser_MDF3mm.pdf"


@unittest.skipUnless(os.path.exists(PDF), "PDF da Carine V2 não está neste PC")
class DouglasTest(unittest.TestCase):
    def test_projeto(self):
        import douglas as dg
        import maria_olivia as mo
        import presepio as pr
        from scipy.ndimage import label
        pecas = dg.ler(PDF)
        self.assertEqual(set(pecas), set(dg.NOMES))
        # nome: uma peça só, pousada na borda de cima de F02 com o pé das letras acima da janela da foto
        n = pecas["N01"]
        nome = mo._area_util(n["cont"], [p for p, t in n["partes"] if t == "furo"])
        caixa = nome.boundingRect().adjusted(-2, -2, 2, 2)
        self.assertEqual(label(pr._raster([nome], caixa, res=10))[1], 1)
        f02 = pecas["F02"]
        janela = next(p for p, t in f02["partes"] if t == "furo" and p.boundingRect().width() > 100)
        sobre = nome.intersected(janela)
        self.assertTrue(sobre.isEmpty() or pr._area(sobre) < 0.5)  # o nome não cobre a foto
        self.assertAlmostEqual(n["cont"].boundingRect().width(), 196, delta=0.5)  # o Carine do PDF, 1:1
        # rebaixo cobre todo o nome que pousa no MDF e não sai da frente
        reb = next(p for p, t in f02["partes"] if t == "rebaixo")
        solido = mo._area_util(f02["cont"], [p for p, t in f02["partes"] if t == "furo"])
        falta = nome.intersected(solido).subtracted(reb)
        self.assertLess(pr._area(falta) if not falta.isEmpty() else 0, 0.5)
        fora = reb.subtracted(solido)
        self.assertLess(pr._area(fora) if not fora.isEmpty() else 0, 0.5)
        # trio gravado na F02
        self.assertGreater(sum(p.elementCount() for p, t in f02["partes"] if t == "linha"), 5000)
        saida = os.path.join(tempfile.mkdtemp(), "d.rbl")
        chapas = dg.gerar(PDF, saida, os.path.join(tempfile.mkdtemp(), "m.pdf"), os.path.join(tempfile.mkdtemp(), "p.png"))
        self.assertEqual(len(chapas), 3)
        with open(saida, encoding="utf-8") as f:
            d = json.load(f)
        cam = {c["id"]: c for c in d["camadas"]}
        self.assertEqual(set(cam), {"C10", "C04", "C05", "C06", "C02", "C01"})
        self.assertEqual(cam["C10"]["intervalo_mm"], 0.15)  # 1 mm + contorno não deu certo (dono, 19/11)
        self.assertFalse(cam["C10"]["subcamadas"])
        self.assertEqual((cam["C10"]["velocidade_mm_min"], cam["C10"]["potencia_max"], cam["C10"]["passadas"]),
                         (1500.0, 60.0, 1))
        self.assertTrue(all(c["potencia_max"] <= 85 for c in d["camadas"]))
        self.assertTrue(all(cam[k]["velocidade_mm_min"] == 630.0 for k in ("C05", "C06", "C02", "C01")))


if __name__ == "__main__":
    unittest.main()
