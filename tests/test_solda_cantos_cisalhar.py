"""Solda/união mantém o que está dentro; ciclo do canto (redondo → 45° → vivo); cisalhar pelas alças do meio."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import nos  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def pontos(p):
    return [(round(p.elementAt(i).x, 4), round(p.elementAt(i).y, 4)) for i in range(p.elementCount())]


class CicloDoCantoTest(unittest.TestCase):
    def test_redondo_45_e_vivo(self):
        ret = fm.rect_path(QRectF(0, 0, 100, 40))
        canto = next(c for c in nos.cantos_boleaveis(ret) if c[2] == (100, 0))
        redondo, n = nos.bolear(ret, 8, [canto[:2]])
        self.assertEqual(n, 1)
        arco = nos.cantos_redondos(redondo)
        self.assertEqual(len(arco), 1)
        chanfro = nos.chanfrar(redondo, *arco[0][:2])
        self.assertEqual(nos.cantos_redondos(chanfro), [])
        ch = nos.chanfros(chanfro)
        self.assertEqual(len(ch), 1)
        self.assertEqual(tuple(round(v, 6) for v in ch[0][2]), (96.0, 4.0))  # meio da reta de 45° (recuo de 8 nos dois lados)
        vivo = nos.canto_vivo(chanfro, *ch[0][:2])
        self.assertEqual(sorted(set(pontos(vivo))), sorted(set(pontos(ret))))  # voltou ao retângulo
        self.assertEqual(nos.chanfros(ret), [])  # lados do retângulo não são chanfro


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.show_error = self.w.show_info = lambda *a: None
        self.w.resize(1400, 900)
        self.w.show()
        app.processEvents()
        self.w.new_document()
        self.view = self.w.canvas.view

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def add(self, nome, path):
        s = ob.Shape(path, nome, "C01", "#2f6bff")
        self.w._edit("t", lambda: self.view.scene().addItem(s))
        return next(x for x in self.view.shapes() if x.name == nome)

    def test_solda_nao_engole_o_que_esta_dentro(self):
        placa = self.add("Placa", fm.rect_path(QRectF(100, 100, 100, 50)))
        pega = self.add("Pega", fm.rect_path(QRectF(190, 110, 40, 30)))  # sobrepõe a borda: junta
        furo = self.add("Furo", fm.ellipse_path(QRectF(120, 115, 20, 20)))  # inteiro dentro: fica
        for s in (placa, pega, furo):
            s.setSelected(True)
        self.assertTrue(self.w.booleana("solda"))
        nomes = sorted(s.name for s in self.view.shapes())
        self.assertEqual(nomes, ["Furo", "Solda"])
        solda = next(s for s in self.view.shapes() if s.name == "Solda")
        r = ob.geom_rect(solda)
        self.assertEqual((r.left(), r.right()), (100, 230))  # placa + pega numa forma só

    def test_ciclo_pelo_clique(self):
        placa = self.add("Placa", fm.rect_path(QRectF(100, 100, 120, 40)))
        self.view.ajustar_a(QRectF(80, 80, 160, 80))
        app.processEvents()
        self.w.tools["bolear"].trigger()
        self.w.raio_bolear.setValue(10)
        self.assertTrue(self.w.bolear_em(QPointF(100.5, 100.5)))  # redondo
        placa = next(s for s in self.view.shapes() if s.name == "Placa")
        meio_arco = nos.cantos_redondos(placa.path())[0][2]
        self.assertTrue(self.w.bolear_em(QPointF(*meio_arco)))  # 45°
        placa = next(s for s in self.view.shapes() if s.name == "Placa")
        self.assertEqual(len(nos.chanfros(placa.path())), 1)
        meio_chanfro = nos.chanfros(placa.path())[0][2]
        self.assertTrue(self.w.bolear_em(QPointF(*meio_chanfro)))  # vivo
        placa = next(s for s in self.view.shapes() if s.name == "Placa")
        self.assertEqual(len(fm.nodes(placa.path())), 4)

    def test_cisalhar_arrastando(self):
        placa = self.add("Placa", fm.rect_path(QRectF(100, 100, 100, 50)))
        self.view.scene().clearSelection()
        placa.setSelected(True)
        self.view.ajustar_a(QRectF(60, 60, 200, 140))
        app.processEvents()
        self.w.interruptores["cisalhar"].setChecked(True)
        alca = dict(self.view.overlay.handle_points())["n"]  # meio de cima
        self.assertEqual(self.view.handle_at(self.view.mapFromScene(alca)), "n")
        vp = self.view.viewport()

        def ev(k, pt, b, bs):
            pos = self.view.mapFromScene(pt)
            app.sendEvent(vp, QMouseEvent(k, QPointF(pos), QPointF(vp.mapToGlobal(pos)), b, bs, Qt.NoModifier))
            app.processEvents()
        ev(QEvent.MouseButtonPress, alca, Qt.LeftButton, Qt.LeftButton)
        ev(QEvent.MouseMove, alca + QPointF(10, 0), Qt.NoButton, Qt.LeftButton)
        ev(QEvent.MouseMove, alca + QPointF(20, 0), Qt.NoButton, Qt.LeftButton)
        ev(QEvent.MouseButtonRelease, alca + QPointF(20, 0), Qt.LeftButton, Qt.NoButton)
        placa = next(s for s in self.view.shapes() if s.name == "Placa")
        topo = placa.sceneTransform().map(QPointF(100, 100))
        base = placa.sceneTransform().map(QPointF(100, 150))
        self.assertAlmostEqual(base.x(), 100, delta=0.6)  # a base fica
        self.assertAlmostEqual(topo.x() - base.x(), 20, delta=1.5)  # o topo andou: tirou do esquadro
        self.assertAlmostEqual(ob.geom_rect(placa).height(), 50, delta=1e-6)  # altura não mudou
        self.w.interruptores["cisalhar"].setChecked(False)


class DicasAnimadasTest(unittest.TestCase):
    def test_todas_as_demos_desenham_e_instalam(self):
        from PySide6.QtCore import QPoint
        from redblack.ui.dica_animada import DEMOS, DicaAnimada
        d = DicaAnimada()
        for nome, demo in DEMOS.items():
            for t in (0.0, 0.33, 0.66, 0.99):
                d.mostrar(nome, "Texto de ajuda bem comprido para quebrar em mais de uma linha na janelinha.", demo,
                          QPoint(0, 0))
                d.t = t
                d.grab()  # desenha sem erro em vários momentos
        d.esconder()
        with tempfile.TemporaryDirectory() as tmp:
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            self.assertEqual(w.tools["bolear"].property("demo"), "bolear")
            self.assertEqual(w.tools["star"].property("demo"), "star")
            w.close()


if __name__ == "__main__":
    unittest.main()
