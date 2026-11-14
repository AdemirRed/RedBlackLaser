"""Formas prontas (menu suspenso), contorno retangular ao redor, pesquisa de comandos (F4) e raio do Bolear."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401  (mesa 400 x 400 dos testes)

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import formas_prontas as fp  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.dialogo_pesquisa import DialogoPesquisa, coletar_comandos  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class CatalogoTest(unittest.TestCase):
    def test_todas_preenchem_a_caixa(self):
        caixa = QRectF(10, 20, 80, 50)
        for nome in fp.CATALOGO:
            r = fp.forma_pronta(nome, caixa).boundingRect()
            for got, exp in zip((r.x(), r.y(), r.width(), r.height()), (10, 20, 80, 50)):
                self.assertAlmostEqual(got, exp, places=4, msg=nome)
        self.assertTrue(fp.forma_pronta("Estrela de 5 pontas", QRectF(0, 0, 0, 10)).isEmpty())
        self.assertIn("Estrelas", fp.grupos())


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.w.new_document()
        self.view = self.w.canvas.view

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def test_menu_suspenso_nos_botoes(self):
        from PySide6.QtWidgets import QToolButton
        bt = self.w.barra_ferramentas.findChild(QToolButton, "grupo_Formas")  # formas agrupadas num botão
        acoes = bt.menu().actions()
        for k in ("rect", "ellipse", "polygon", "star"):
            self.assertIn(self.w.tools[k], acoes)
        prontas = next(a.menu() for a in acoes if a.menu())
        textos = [a.text() for a in prontas.actions()]
        self.assertIn("Coração", textos)
        self.assertIn("Oblongo (pega)", textos)

    def test_desenhar_forma_pronta(self):
        self.w.usar_forma_pronta("Coração")
        vp = self.view.viewport()
        a, b = self.view.mapFromScene(QPointF(50, 50)), self.view.mapFromScene(QPointF(110, 100))
        QTest.mousePress(vp, Qt.LeftButton, Qt.AltModifier, a)
        QTest.mouseMove(vp, b)
        QTest.mouseRelease(vp, Qt.LeftButton, Qt.AltModifier, b)
        s = self.view.shapes()[-1]
        self.assertEqual(s.name, "Coração 1")
        r = ob.geom_rect(s)
        self.assertAlmostEqual(r.width(), 60, delta=1)

    def test_contorno_ao_redor_do_circulo(self):
        self.w.create_shape(fm.ellipse_path(QRectF(100, 100, 40, 40)), "ellipse")
        self.assertTrue(self.w.contorno_ao_redor({"margem": 5.0, "raio": 0.0, "quadrado": False}))
        novo = self.view.shapes()[-1]
        r = ob.geom_rect(novo)
        self.assertEqual((r.x(), r.y(), r.width(), r.height()), (95, 95, 50, 50))
        self.assertEqual(len(fm.nodes(novo.path())), 4)  # retângulo de cantos vivos, não outro círculo

    def test_pesquisa_f4(self):
        cmds = coletar_comandos(self.w)
        self.assertTrue(any(t.startswith("Bolear") for t, _c, _a in cmds))
        dlg = DialogoPesquisa(self.w)
        dlg.busca.setText("bolear")
        self.assertGreaterEqual(dlg.lista.count(), 1)
        dlg.busca.setText("configuracoes")  # sem acento acha "Configurações"
        self.assertGreaterEqual(dlg.lista.count(), 1)
        self.w.create_shape(fm.rect_path(QRectF(10, 10, 20, 20)), "rect")  # o comando pede uma seleção
        self.w.select_all()
        self.w._on_selection()
        self.assertTrue(self.w.act_contorno_redor.isEnabled(),
                        f"seleção={len(self.w._sel())} formas={len(self.view.shapes())}")
        dlg = DialogoPesquisa(self.w)  # a pesquisa é aberta depois de selecionar, como no uso real
        dlg.busca.setText("contorno redor")
        dlg.executar()
        self.assertIsNotNone(dlg.escolhida, (dlg.busca.text(), len(dlg.comandos),
                                             [t for t, _c, _a in dlg.comandos if "ontorno" in t],
                                             [(m.text(), len(m.menu().actions()) if m.menu() else None)
                                              for m in self.w.menuBar().actions()]))
        self.assertIn("Contorno retangular", dlg.escolhida.text())
        self.assertEqual(self.w.act_pesquisa.shortcut().toString(), "F4")

    def test_raio_do_bolear_visivel(self):
        self.w.raio.setValue(0)
        self.w.tools["bolear"].trigger()
        self.assertEqual(self.w.lb_raio.text().strip(), "Raio do bolear")
        self.assertEqual(self.w.raio.value(), 5)  # zerado vira 5 mm para começar
        self.w.tools["select"].trigger()
        self.assertEqual(self.w.lb_raio.text().strip(), "Raio")


if __name__ == "__main__":
    unittest.main()
