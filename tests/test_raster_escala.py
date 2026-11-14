"""Imagem reduzida/ampliada: a grade de gravação usa o tamanho REAL na mesa (intervalo de linhas certo)."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QColor, QImage, QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import importar_imagem as imgimp  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack import raster  # noqa: E402

app = QApplication.instance() or QApplication([])


class RasterEscalaTest(unittest.TestCase):
    def test_imagem_reduzida_usa_o_tamanho_na_mesa(self):
        img = QImage(400, 200, QImage.Format_RGB32)
        img.fill(QColor(90, 90, 90))
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        res = imgimp.from_bytes(bytes(buf.data()), "a.png")
        s = ob.ImageShape(res.imagem, 200, 100, "Foto")  # importada com 200 × 100 mm…
        s.setTransform(QTransform.fromScale(0.25, 0.25) * QTransform.fromTranslate(10, 10))  # …reduzida a 50 × 25
        grades = []
        original = raster.grade

        def espiao(*a, **k):
            r = original(*a, **k)
            grades.append((r[1], r[2]))
            return r
        raster.grade = espiao
        try:
            c = cm.alterar(cm.Camada("C00", "img"), modo="imagem", modo_imagem="limiar", intervalo_mm=0.5)
            perc = pc.gerar([s.snapshot()], [c])
        finally:
            raster.grade = original
        self.assertEqual(grades, [(100, 50)])  # 50 mm / 0,5 = 100 pontos (não 400)
        W, H = gc.area(gc.PERFIL)
        ys = sorted({round(t.pontos[0][1], 3) for t in perc.trechos if t.tipo != "vazio"})
        passos = {round(b - a, 3) for a, b in zip(ys, ys[1:])}
        self.assertEqual(passos, {0.5})  # linhas a 0,5 mm na peça
        xs = [p[0] for t in perc.trechos if t.tipo != "vazio" for p in t.pontos]
        self.assertAlmostEqual(min(xs), 10, delta=0.01)
        self.assertAlmostEqual(max(xs), 60, delta=0.01)

    def test_imagem_varre_na_vertical_com_90_graus(self):
        img = QImage(400, 200, QImage.Format_RGB32)
        img.fill(QColor(255, 255, 255))
        for y in range(200):
            for x in range(100):  # só o quarto da esquerda é preto
                img.setPixelColor(x, y, QColor(0, 0, 0))
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        res = imgimp.from_bytes(bytes(buf.data()), "a.png")
        s = ob.ImageShape(res.imagem, 40, 20, "Foto")
        s.setTransform(QTransform.fromTranslate(10, 10))
        for ang, vertical in ((0, False), (90, True)):
            c = cm.alterar(cm.Camada("C00", "img"), modo="imagem", modo_imagem="limiar", intervalo_mm=0.5,
                           angulo_graus=ang)
            cortes = [t for t in pc.gerar([s.snapshot()], [c]).trechos if t.tipo == "corte"]
            xs = [p[0] for t in cortes for p in t.pontos]
            ys = [p[1] for t in cortes for p in t.pontos]
            self.assertAlmostEqual(min(xs), 10, delta=0.3)  # mesma área nos dois sentidos: o quarto da esquerda
            self.assertAlmostEqual(max(xs), 20, delta=0.3)
            self.assertAlmostEqual(max(ys) - min(ys), 20, delta=0.6)
            mesma_x = all(abs(t.pontos[0][0] - t.pontos[-1][0]) < 1e-6 for t in cortes)
            self.assertEqual(mesma_x, vertical)

    def test_retomar_de_restaura_estado(self):
        L = ["G21", "G90", "M5", "M4 S0", "M8", "G0 X10.000 Y10.000", "G1 X20.000 Y10.000 S300 F1200",
             "G1 X20.000 Y20.000", "G0 X50.000 Y50.000", "G1 X60.000 Y50.000 S500", "M5", "M9", "M2"]
        st = gc.estado_ate(L, 8)
        self.assertEqual((st["x"], st["y"], st["f"], st["s"], st["laser"], st["ar"]), (20, 20, 1200, 300, "M4", True))
        r = gc.retomar_de(L, 7)
        self.assertEqual(r[:7], ["G21", "G90", "M5", "M8", "G0 X20.000 Y10.000", "M4 S300", "G1 F1200"])
        self.assertEqual(r[7:], L[7:])  # o resto igual, termina com M2 do original
        trecho = gc.retomar_de(L, 6, 8)
        self.assertEqual(trecho[-3:], ["M5", "M9", "M2"])  # trecho no meio: desliga laser e ar no fim

    def test_corte_em_m3_com_perfil_m4(self):
        from PySide6.QtCore import QRectF
        from redblack import formas as fm
        antes = gc.PERFIL
        try:
            corte = cm.Camada("C01", "corte", "linha", 300, 80, 0, 1, 0.1)
            grav = cm.Camada("C02", "grav", "preenchimento", 3000, 20, 0, 1, 0.5)
            sn = [(fm.rect_path(QRectF(10, 10, 20, 20)), QTransform(), "a", "C02", "#fff", None),
                  (fm.rect_path(QRectF(50, 10, 20, 20)), QTransform(), "b", "C01", "#fff", None)]
            gc.definir_perfil("M4", 1000, 20000, True)
            t = gc.gerar(pc.gerar(sn, [grav, corte]), [grav, corte])
            cmds = [ln.split()[0] for ln in t.splitlines() if ln.startswith(("M3", "M4"))]
            self.assertEqual(cmds, ["M4", "M3"])  # gravação dinâmica, corte constante
            self.assertTrue(gc.analisar(t)["fim_desligado"])
            gc.definir_perfil("M4", 1000, 20000, False)  # opção desligada: tudo em M4, como antes
            t = gc.gerar(pc.gerar(sn, [grav, corte]), [grav, corte])
            self.assertEqual([ln.split()[0] for ln in t.splitlines() if ln.startswith(("M3", "M4"))], ["M4"])
        finally:
            gc.PERFIL = antes

    def test_air_assist_no_gcode(self):
        from PySide6.QtCore import QRectF
        from redblack import formas as fm
        a = ob.Shape(fm.rect_path(QRectF(10, 10, 20, 20)), "A", "C01", "#2f6bff")
        b = ob.Shape(fm.rect_path(QRectF(50, 10, 20, 20)), "B", "C02", "#e0313b")
        camadas = [cm.alterar(cm.Camada("C02", "sem ar"), air=False), cm.alterar(cm.Camada("C01", "com ar"), air=True)]
        texto = gc.gerar(pc.gerar([b.snapshot(), a.snapshot()], camadas), camadas)
        linhas = [ln.split(";")[0].strip() for ln in texto.splitlines()]
        self.assertIn("M8", linhas)
        self.assertLess(linhas.index("M8"), len(linhas) - 1)
        self.assertEqual([x for x in linhas if x in ("M8", "M9")], ["M8", "M9"])  # liga na camada com ar, desliga no fim
        self.assertTrue(gc.analisar(texto)["fim_desligado"])
        todo = [ln.split(";")[0].strip() for ln in gc.ar_no_trabalho_todo(texto).splitlines()]
        self.assertEqual([x for x in todo if x in ("M8", "M9")], ["M8", "M9"])  # liga uma vez, desliga no fim
        primeiro_mov = next(k for k, x in enumerate(todo) if x.startswith(("G0", "G1")))
        self.assertLess(todo.index("M8"), primeiro_mov)
        self.assertLess(todo.index("M9"), todo.index("M2"))


if __name__ == "__main__":
    unittest.main()
