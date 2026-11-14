"""Gravação de imagens: branco nunca grava; limiar, pontilhado e tons de cinza."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import importar_imagem as im  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack import raster  # noqa: E402

app = QApplication.instance() or QApplication([])


def imagem(pintar):
    img = QImage(100, 100, QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    pintar(p)
    p.end()
    ba = QByteArray()
    b = QBuffer(ba)
    b.open(QIODevice.WriteOnly)
    img.save(b, "PNG")
    r = im.from_bytes(bytes(ba), "t.png")
    return ob.ImageShape(r.imagem, 20, 20, "img", "C00")  # 20 × 20 mm


def camada(**kw):
    return cm.alterar(cm.nova("C00", imagem=True), intervalo_mm=0.5, potencia_max=80, potencia_min=10, **kw)


def cortes(p):
    return [t for t in p.trechos if t.tipo == "corte"]


class RasterTest(unittest.TestCase):
    def test_branco_nao_grava(self):
        s = imagem(lambda p: None)
        for modo in raster.MODOS:
            self.assertEqual(cortes(pc.gerar([s.snapshot()], [camada(modo_imagem=modo)])), [], modo)

    def test_metade_preta_no_limiar(self):
        s = imagem(lambda p: p.fillRect(0, 0, 50, 100, QColor("black")))
        p = pc.gerar([s.snapshot()], [camada(modo_imagem="limiar")])
        cs = cortes(p)
        self.assertEqual(len(cs), 40)                                         # 20 mm / 0,5 mm
        self.assertAlmostEqual(p.comprimento_corte, 40 * 10, 6)              # só a metade esquerda
        self.assertTrue(all(max(q[0] for q in t.pontos) <= 10 + 1e-9 for t in cs))
        neg = pc.gerar([s.snapshot()], [camada(modo_imagem="limiar", negativo=True)])
        self.assertTrue(all(min(q[0] for q in t.pontos) >= 10 - 1e-9 for t in cortes(neg)))

    def test_cinza_varia_potencia_e_gcode(self):
        def degrade(p):
            for x in range(100):
                p.fillRect(x, 0, 1, 100, QColor(255 - x * 2, 255 - x * 2, 255 - x * 2))
        s = imagem(degrade)
        c = camada(modo_imagem="cinza")
        p = pc.gerar([s.snapshot()], [c])
        pots = {t.potencia for t in cortes(p)}
        self.assertGreater(len(pots), 10)
        self.assertTrue(all(10 <= x <= 80 for x in pots))
        texto = gc.gerar(p, [c])
        ss = {int(w[1:]) for w in texto.split() if w.startswith("S") and w[1:].isdigit()}
        self.assertGreater(len(ss), 10)                                       # S varia no G-code
        self.assertLessEqual(max(ss), 800)

    def test_pontilhado_cinza_medio_metade_dos_pontos(self):
        s = imagem(lambda p: p.fillRect(0, 0, 100, 100, QColor(128, 128, 128)))
        p = pc.gerar([s.snapshot()], [camada(modo_imagem="pontilhado")])
        frac = p.comprimento_corte / (40 * 20)
        self.assertAlmostEqual(frac, 0.5, delta=0.08)

    def test_imagem_girada_acompanha(self):
        s = imagem(lambda p: p.fillRect(0, 0, 100, 100, QColor("black")))
        ob.rotate([s], 90, ob.bounds([s]).center())
        p = pc.gerar([s.snapshot()], [camada(modo_imagem="limiar")])
        t = cortes(p)[0]
        self.assertAlmostEqual(t.pontos[0][0], t.pontos[1][0], 6)            # linhas viraram verticais

    def test_grande_demais(self):
        with self.assertRaises(raster.RasterGrandeDemais):
            raster.grade(QImage(10, 10, QImage.Format_RGB32), 10000, 10000, 0.01)



class AjusteTest(unittest.TestCase):
    def test_ajustar(self):
        lin = [[0, 128, 255]]
        self.assertEqual(raster.ajustar(lin), lin)                            # neutro: igual
        self.assertEqual(raster.ajustar(lin, brilho_pct=100)[0], [255, 255, 255])
        self.assertLess(raster.ajustar(lin, brilho_pct=-20)[0][1], 128)
        alto = raster.ajustar(lin, contraste_pct=100)[0]
        self.assertEqual((alto[0], alto[2]), (0, 255))
        self.assertGreater(raster.ajustar(lin, gama=2.0)[0][1], 128)          # gama > 1 clareia os meios-tons

    def test_brilho_total_nao_grava(self):
        s = imagem(lambda p: p.fillRect(0, 0, 100, 100, QColor(60, 60, 60)))
        self.assertGreater(len(cortes(pc.gerar([s.snapshot()], [camada(modo_imagem="limiar")]))), 0)
        self.assertEqual(cortes(pc.gerar([s.snapshot()], [camada(modo_imagem="limiar", brilho_pct=100)])), [])



class LinhaRasterTest(unittest.TestCase):
    def test_vaos_em_g1_e_sobrevarredura_so_nas_pontas(self):
        def listras(p):
            for x in range(0, 100, 20):
                p.fillRect(x, 0, 10, 100, QColor("black"))                    # 5 faixas pretas por linha
        s = imagem(listras)
        ob.move_by([s], 50, 50)                                               # longe da borda: cabe a sobrevarredura
        c = camada(modo_imagem="limiar", sobrevarredura_mm=3)
        p = pc.gerar([s.snapshot()], [c])
        linhas = 40
        self.assertEqual(len(cortes(p)), linhas * 5)
        vazios = [t for t in p.trechos if t.tipo == "vazio"]
        self.assertEqual(len(vazios), linhas + 1)                             # uma aproximação por linha + volta
        sobras = [t for t in p.trechos if t.tipo == "sobra"]
        self.assertEqual(len(sobras), linhas * (2 + 4))                       # 2 pontas + 4 vãos por linha
        self.assertEqual(sum(abs(t.comprimento - 3) < 1e-9 for t in sobras), linhas * 2)
        texto = gc.gerar(p, [c])
        self.assertTrue(gc.analisar(texto)["fim_desligado"])



class DitherTest(unittest.TestCase):
    def test_todos_os_pontilhados_mantem_o_tom_medio(self):
        for modo in ("pontilhado", "jarvis", "stucki", "atkinson"):
            lin = [[128] * 40 for _ in range(40)]
            pot = raster.potencias(lin, modo, 50, 0, 80)
            frac = sum(v > 0 for row in pot for v in row) / 1600
            self.assertAlmostEqual(frac, 0.5, delta=0.1, msg=modo)
            branco = raster.potencias([[255] * 10 for _ in range(10)], modo, 50, 0, 80)
            self.assertEqual(sum(map(sum, branco)), 0, modo)                  # branco nunca grava
        self.assertEqual(set(raster.MODOS), set(cm.MODOS_IMAGEM))


if __name__ == "__main__":
    unittest.main()
