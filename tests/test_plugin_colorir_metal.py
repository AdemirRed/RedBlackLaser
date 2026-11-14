"""Plugin Colorir metal: grade de teste, leitura da foto, paletas e aplicação às formas."""
import os
import re
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.plugins.colorir_metal import cores as co  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class GradeTest(unittest.TestCase):
    def test_grade_padrao_como_no_anuncio(self):
        cfg = dict(co.GRADE_PADRAO)
        self.assertEqual(co.potencias(cfg), [25, 30, 35, 40, 45, 50, 55])
        self.assertEqual(len(co.celulas(cfg)), 70)
        txt, perc = co.gcode_grade(cfg)
        s = sorted({int(v) for v in re.findall(r"S(\d+)", txt)})
        self.assertEqual(s, [0, 250, 300, 350, 400, 450, 500, 550, 600])  # 25…55 % + rótulos a 60 %
        self.assertIn("F4000", txt)
        # quadrado de 0,10 mm: 8 mm / 0,1 = ~80 linhas; de 0,01 mm: ~800
        linhas = {c: sum(1 for t in perc.trechos if t.camada == c and t.tipo != "vazio") for c in ("T001", "T010")}
        self.assertGreater(linhas["T001"], 700)
        self.assertLess(linhas["T010"], 100)

    def test_paleta_referencia(self):
        p = co.paleta_referencia()
        self.assertEqual(len(p["cores"]), 70)
        azul = next(c for c in p["cores"] if c.potencia == 30 and abs(c.intervalo - 0.03) < 1e-9)
        self.assertEqual(azul.cor, "#6da2fc")
        self.assertIs(co.mais_proxima(p["cores"], "#6aa0ff"), azul)


class FotoEPaletaTest(unittest.TestCase):
    def test_ler_foto_e_salvar(self):
        cores = [["#ff0000", "#00ff00", "#0000ff"], ["#ffff00", "#00ffff", "#ff00ff"]]
        img = QImage(400, 300, QImage.Format_RGB32)
        img.fill(QColor("#888888"))
        p = QPainter(img)
        for i, lin in enumerate(cores):
            for j, c in enumerate(lin):
                p.fillRect(50 + j * 120 - 30, 80 + i * 120 - 30, 60, 60, QColor(c))
        p.end()
        lidas = co.ler_foto(img, QPointF(50, 80), QPointF(290, 200), 2, 3)
        self.assertEqual(lidas, cores)
        cfg = dict(co.GRADE_PADRAO, pot_ini=30, pot_fim=40, pot_passo=10, intervalos=(0.02, 0.04, 0.06))
        pal = co.paleta_da_foto("Teste", lidas, cfg)
        self.assertEqual((pal["cores"][4].cor, pal["cores"][4].potencia, pal["cores"][4].intervalo),
                         ("#00ffff", 40, 0.04))
        with tempfile.TemporaryDirectory() as tmp:
            arq = os.path.join(tmp, "x", "paletas.json")
            co.salvar(arq, [co.paleta_referencia(), pal])
            de_volta = co.carregar(arq)
            self.assertEqual([x["nome"] for x in de_volta], [co.paleta_referencia()["nome"], "Teste"])
            self.assertEqual(de_volta[1]["cores"], pal["cores"])
            self.assertEqual(co.carregar(os.path.join(tmp, "nao_existe.json"))[0]["referencia"], True)


class AplicarTest(unittest.TestCase):
    def test_plugin_na_janela_aplica_cores(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            w.show()
            app.processEvents()
            w.new_document()
            v = w.canvas.view
            for k in range(2):
                s = ob.Shape(fm.rect_path(QRectF(10 + 30 * k, 10, 20, 20)), f"P{k}", "C01", "#2f6bff")
                w._edit("t", lambda s=s: v.scene().addItem(s))
            self.assertIn("plano_corte", w.plugins_carregados if hasattr(w, "plugins_carregados") else
                          ["plano_corte"])
            jan = w.plugin_colorir_metal["abrir"]()
            jan.arquivo = os.path.join(tmp, "paletas.json")
            azul = co.paleta_referencia()["cores"][12]  # 30 %, 0,03 mm
            vermelho = co.paleta_referencia()["cores"][14]
            with self.assertRaises(ValueError):
                co.aplicar(w, azul)  # nada selecionado
            a, b = v.shapes()
            a.setSelected(True)
            lid_a = jan.aplicar(azul)
            c = w.layer(lid_a)
            self.assertEqual((c.modo, c.potencia_max, c.intervalo_mm, c.velocidade_mm_min),
                             ("preenchimento", 30, 0.03, 4000))
            self.assertTrue(c.nome.startswith("Cor #6da2fc"))
            v.scene().clearSelection()
            next(s for s in v.shapes() if s.name == "P1").setSelected(True)
            lid_b = jan.aplicar(vermelho)
            self.assertNotEqual(lid_a, lid_b)  # cor diferente, camada diferente
            v.scene().clearSelection()
            next(s for s in v.shapes() if s.name == "P1").setSelected(True)
            self.assertEqual(jan.aplicar(azul), lid_a)  # mesma cor reaproveita a camada
            self.assertTrue(jan.salvar_gcode(os.path.join(tmp, "grade.gcode")))
            self.assertGreater(os.path.getsize(os.path.join(tmp, "grade.gcode")), 10000)
            jan.vista_grade.resize(500, 350)
            jan.vista_grade.grab()
            jan.close()
            w.close()


if __name__ == "__main__":
    unittest.main()
