"""Colar imagem/texto/SVG de outros programas; janela Traçar imagem com as opções do original."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QMimeData, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import tracar as trc  # noqa: E402
from redblack.ui.dialogo_tracar import DialogoTracar  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def desenho(w=200, h=100):
    """Fundo branco, quadrado preto à esquerda, círculo cinza-médio à direita, traço fino em cima."""
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.fillRect(10, 30, 50, 50, QColor("black"))
    p.setBrush(QColor(150, 150, 150))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(150, 55), 25, 25)
    p.fillRect(80, 10, 100, 3, QColor("black"))
    p.end()
    return img


def formas(caminho):
    if caminho.isEmpty():
        return 0
    return sum(1 for i in range(caminho.elementCount()) if caminho.elementAt(i).isMoveTo())


class TracarOpcoesTest(unittest.TestCase):
    def test_corte_e_limiar_escolhem_a_faixa_de_brilho(self):
        img = desenho()
        so_preto = trc.tracar_opcoes(img, 200, 100, dict(corte=0, limiar=60, suavidade=0))
        self.assertEqual(formas(so_preto), 2)  # quadrado + traço
        com_cinza = trc.tracar_opcoes(img, 200, 100, dict(corte=0, limiar=200, suavidade=0))
        self.assertEqual(formas(com_cinza), 3)
        so_cinza = trc.tracar_opcoes(img, 200, 100, dict(corte=100, limiar=200, suavidade=0))
        self.assertEqual(formas(so_cinza), 1)
        self.assertGreater(so_cinza.boundingRect().left(), 120)

    def test_suavidade_cria_curvas_e_area_limita(self):
        img = desenho()
        curvo = trc.tracar_opcoes(img, 200, 100, dict(limiar=200, suavidade=1.0))
        self.assertTrue(any(curvo.elementAt(i).isCurveTo() for i in range(curvo.elementCount())))
        reto = trc.tracar_opcoes(img, 200, 100, dict(limiar=200, suavidade=0))
        self.assertFalse(any(reto.elementAt(i).isCurveTo() for i in range(reto.elementCount())))
        parte = trc.tracar_opcoes(img, 200, 100, dict(limiar=200, area=(0.6, 0.2, 0.4, 0.8)))
        self.assertEqual(formas(parte), 1)  # só o círculo

    def test_ignorar_e_transparencia(self):
        img = desenho()
        self.assertEqual(formas(trc.tracar_opcoes(img, 200, 100, dict(limiar=60, ignorar=400))), 1)  # sem o traço
        alfa = QImage(100, 100, QImage.Format_ARGB32)
        alfa.fill(Qt.transparent)
        p = QPainter(alfa)
        p.fillRect(20, 20, 60, 60, QColor(255, 255, 255))  # branco opaco: só a transparência acha
        p.end()
        self.assertEqual(formas(trc.tracar_opcoes(alfa, 100, 100, dict(limiar=128))), 0)
        r = trc.tracar_opcoes(alfa, 100, 100, dict(transparencia=True, suavidade=0)).boundingRect()
        self.assertEqual((round(r.x()), round(r.width())), (20, 60))

    def test_linha_central_vira_um_traco(self):
        img = QImage(120, 40, QImage.Format_ARGB32)
        img.fill(QColor("white"))
        p = QPainter(img)
        p.fillRect(10, 15, 100, 9, QColor("black"))
        p.end()
        c = trc.tracar_opcoes(img, 120, 40, dict(limiar=128, linha_central=True, suavidade=0, otimizar=1))
        self.assertEqual(formas(c), 1)
        r = c.boundingRect()
        self.assertLess(r.height(), 2)  # uma linha no meio, não o contorno da faixa
        self.assertAlmostEqual(r.center().y(), 19.5, delta=1.5)
        self.assertGreater(r.width(), 85)

    def test_esboco_acha_tracos_em_fundo_irregular(self):
        img = QImage(200, 100, QImage.Format_ARGB32)
        p = QPainter(img)
        for x in range(200):  # fundo que escurece da esquerda (branco) para a direita (cinza)
            v = 250 - x // 2
            p.fillRect(x, 0, 1, 100, QColor(v, v, v))
        p.fillRect(150, 20, 4, 60, QColor(70, 70, 70))  # traço de lápis no lado escuro
        p.end()
        normal = trc.tracar_opcoes(img, 200, 100, dict(limiar=170, suavidade=0))
        self.assertGreater(normal.boundingRect().width(), 30)  # o fundo escuro vira mancha
        esboco = trc.tracar_opcoes(img, 200, 100, dict(limiar=170, esboco=True, suavidade=0))
        r = esboco.boundingRect()
        self.assertTrue(140 <= r.left() and r.right() <= 160, r)  # só o traço


class TracadoComplexoTest(unittest.TestCase):
    def test_area_de_clique_de_traçado_enorme_nao_trava(self):
        """Traçado de foto (dezenas de milhares de pontos): a união booleana travava o programa por minutos."""
        import random
        import time
        random.seed(3)
        img = QImage(900, 600, QImage.Format_ARGB32)
        img.fill(QColor("white"))
        p = QPainter(img)
        p.setPen(Qt.NoPen)
        for _ in range(3000):
            v = random.randint(0, 255)
            p.setBrush(QColor(v, v, v))
            p.drawEllipse(QPointF(random.uniform(0, 900), random.uniform(0, 600)), random.uniform(1, 8),
                          random.uniform(1, 8))
        p.end()
        cam = trc.tracar_opcoes(img, 150, 100, dict(limiar=128))
        self.assertGreater(cam.elementCount(), ob.COMPLEXO)
        s = ob.Shape(cam, "Traçado", "C01", "#2f6bff")
        t0 = time.time()
        area = s.shape()
        self.assertLess(time.time() - t0, 2.0)
        self.assertTrue(area.contains(cam.boundingRect().center()))  # clica em qualquer lugar da caixa


class DialogoTracarTest(unittest.TestCase):
    def test_previa_acompanha_as_opcoes(self):
        d = DialogoTracar(desenho())
        n0 = formas(d.previa)
        d.limiar.setValue(200)
        d._refazer()
        self.assertGreater(formas(d.previa), n0)
        d.definir_area((0.6, 0.2, 0.4, 0.8), refazer=False)
        d._refazer()
        self.assertEqual(formas(d.previa), 1)
        d.pontos.setChecked(True)
        d.tela.resize(500, 400)
        d.tela.grab()  # desenha sem erro
        op = d.opcoes()
        self.assertEqual(op["limiar"], 200)
        self.assertEqual(op["area"], (0.6, 0.2, 0.4, 0.8))


class ColarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.show_error = self.w.show_info = lambda *a: None
        self.w.show()
        app.processEvents()
        self.w.new_document()
        self.view = self.w.canvas.view

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def test_colar_imagem(self):
        md = QMimeData()
        md.setImageData(desenho(96, 48))
        self.assertTrue(self.w.colar_do_sistema(md))
        im = [s for s in self.view.shapes() if isinstance(s, ob.ImageShape)]
        self.assertEqual(len(im), 1)
        r = ob.geom_rect(im[0])
        self.assertAlmostEqual(r.width(), 25.4, delta=0.01)  # 96 px a 96 dpi = 1 polegada
        self.assertTrue(self.w.tracar_imagem(dict(limiar=60, apagar_imagem=True)))  # e já dá para traçar
        self.assertFalse(any(isinstance(s, ob.ImageShape) for s in self.view.shapes()))

    def test_colar_texto_e_svg(self):
        md = QMimeData()
        md.setText("RedBlack")
        self.assertTrue(self.w.colar_do_sistema(md))
        t = [s for s in self.view.shapes() if isinstance(s, ob.TextShape)]
        self.assertEqual(t[0].params.texto, "RedBlack")
        md = QMimeData()
        md.setText('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10">'
                   '<rect x="0" y="0" width="20" height="10" fill="none" stroke="black"/></svg>')
        self.assertTrue(self.w.colar_do_sistema(md))
        self.assertEqual(len(self.view.shapes()), 2)

    def test_ajustar_imagem_salvar_bitmap_e_menu(self):
        md = QMimeData()
        md.setImageData(desenho(96, 48))
        self.w.colar_do_sistema(md)
        img = next(s for s in self.view.shapes() if isinstance(s, ob.ImageShape))
        img.setSelected(True)
        self.assertTrue(self.w.ajustar_imagem(dict(modo_imagem="jarvis", brilho_pct=20.0, contraste_pct=10.0,
                                                   gama=1.2, limiar_pct=50.0, intervalo_mm=0.2, negativo=False)))
        c = self.w.layer(img.layer)
        self.assertEqual((c.modo_imagem, c.brilho_pct, c.intervalo_mm), ("jarvis", 20.0, 0.2))
        arq = os.path.join(self.tmp.name, "proc.png")
        self.assertTrue(self.w.salvar_bitmap_processado(arq))
        out = QImage(arq)
        self.assertEqual(out.width(), round(25.4 / 0.2))  # um pixel por linha do laser
        textos = [a.text().replace("&", "") for a in self.w._menu_contexto if a]
        for t in ("Traçar imagem…", "Ajustar imagem…", "Salvar bitmap processado…", "Colar no lugar",
                  "Converter em bitmap", "Bloquear formas selecionadas", "Selecionar tudo"):
            self.assertIn(t, textos)
        from redblack.ui.dialogo_ajustar_imagem import DialogoAjustarImagem
        d = DialogoAjustarImagem(desenho(), 50, 25, c)
        d.modo.setCurrentIndex(0)
        d._refazer()
        self.assertFalse(d.processada.img.isNull())
        d.grab()

    def test_ctrl_v_com_imagem_de_outro_programa(self):
        """A ação Colar (Ctrl+V) precisa estar ativa sem cópia interna, só com a imagem no sistema."""
        self.w._clipboard = []
        QApplication.clipboard().setImage(desenho(96, 48))
        app.processEvents()
        acao = self.w.actions_by_key["paste"]
        self.assertTrue(acao.isEnabled())
        acao.trigger()
        self.assertEqual(sum(isinstance(s, ob.ImageShape) for s in self.view.shapes()), 1)
        QApplication.clipboard().clear()
        app.processEvents()
        self.assertFalse(acao.isEnabled())

    def test_copia_interna_continua_valendo(self):
        s = ob.Shape(fm.rect_path(QRectF(10, 10, 20, 20)), "Q", "C01", "#2f6bff")
        self.w._edit("t", lambda: self.view.scene().addItem(s))
        s = self.view.shapes()[0]
        s.setSelected(True)
        self.w.copy()
        self.w.paste()
        self.assertEqual(len(self.view.shapes()), 2)  # colou a cópia, não o texto "Q"
        self.assertFalse(any(isinstance(x, ob.TextShape) for x in self.view.shapes()))


if __name__ == "__main__":
    unittest.main()
