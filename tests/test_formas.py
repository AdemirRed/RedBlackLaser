"""Etapa 8: retângulo, círculo e caminhos editáveis com medidas previsíveis; agrupar/desagrupar."""
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class GeometriaTest(unittest.TestCase):
    def test_caixa_do_arraste(self):
        a = QPointF(10, 10)
        self.assertEqual(fm.drag_rect(a, QPointF(60, 40)).getRect(), (10, 10, 50, 30))
        self.assertEqual(fm.drag_rect(a, QPointF(-40, -20)).getRect(), (-40, -20, 50, 30))  # arraste ao contrário
        self.assertEqual(fm.drag_rect(a, QPointF(60, 40), square=True).getRect(), (10, 10, 50, 50))
        self.assertEqual(fm.drag_rect(a, QPointF(0, 40), square=True).getRect(), (-20, 10, 30, 30))
        self.assertEqual(fm.drag_rect(a, QPointF(30, 15), center=True).getRect(), (-10, 5, 40, 10))
        self.assertEqual(fm.drag_rect(a, QPointF(30, 15), True, True).getRect(), (-10, -10, 40, 40))

    def test_medidas_exatas(self):
        r = QRectF(5, 5, 50, 30)
        self.assertEqual(fm.rect_path(r).boundingRect(), r)
        self.assertEqual(fm.ellipse_path(r).boundingRect(), r)
        circle = fm.ellipse_path(QRectF(0, 0, 40, 40))
        for t in (0.1, 0.33, 0.6, 0.9):  # pontos sobre o círculo (aproximação cúbica < 0,03 %)
            p = circle.pointAtPercent(t)
            self.assertAlmostEqual(math.hypot(p.x() - 20, p.y() - 20), 20, delta=20 * 3e-4)

    def test_poligono_regular(self):
        for n in (3, 5, 6, 8):
            p = fm.polygon_path(QPointF(50, 50), 20, n)
            pts = [p.elementAt(i) for i in range(n)]
            for e in pts:
                self.assertAlmostEqual(math.hypot(e.x - 50, e.y - 50), 20, delta=1e-9)  # raio exato
            self.assertAlmostEqual(pts[0].x, 50, delta=1e-9)
            self.assertAlmostEqual(pts[0].y, 30, delta=1e-9)                              # vértice no topo
            sides = {round(math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y), 9) for i in range(n)}
            self.assertEqual(len(sides), 1)                                              # lados iguais
        hexa = fm.polygon_path(QPointF(0, 0), 10, 6).boundingRect()
        self.assertAlmostEqual(hexa.width(), 10 * math.sqrt(3), delta=1e-9)
        self.assertAlmostEqual(hexa.height(), 20, delta=1e-9)
        with self.assertRaises(ValueError):
            fm.polygon_path(QPointF(0, 0), 10, 2)

    def test_angulo_45(self):
        b = fm.snap_angle(QPointF(0, 0), QPointF(10, 1))
        self.assertAlmostEqual(b.y(), 0, delta=1e-9)
        self.assertAlmostEqual(b.x(), math.hypot(10, 1), delta=1e-9)
        b = fm.snap_angle(QPointF(0, 0), QPointF(10, 9))
        self.assertAlmostEqual(b.x(), b.y(), delta=1e-9)

    def test_nos_do_retangulo_e_da_elipse(self):
        rect = fm.rect_path(QRectF(0, 0, 10, 5))
        self.assertEqual(len(fm.nodes(rect)), 4)                       # sem o ponto duplicado de fechamento
        moved = fm.move_node(rect, fm.nodes(rect)[2], 5, 5)            # canto (10,5) -> (15,10)
        self.assertEqual(moved.boundingRect().getRect(), (0, 0, 15, 10))
        moved0 = fm.move_node(rect, 0, -2, -3)                         # início move também o fechamento
        self.assertEqual((moved0.elementAt(0).x, moved0.elementAt(0).y), (-2.0, -3.0))
        last = moved0.elementAt(moved0.elementCount() - 1)
        self.assertEqual((last.x, last.y), (-2.0, -3.0))
        ell = fm.ellipse_path(QRectF(0, 0, 20, 10))
        self.assertEqual(len(fm.nodes(ell)), 4)
        top = min(fm.nodes(ell), key=lambda i: ell.elementAt(i).y)
        m = fm.move_node(ell, top, 0, -5)
        self.assertAlmostEqual(m.boundingRect().top(), -5, delta=1e-9)   # tangente horizontal preservada
        self.assertAlmostEqual(m.boundingRect().height(), 15, delta=1e-9)

    def test_nos_de_linha_aberta(self):
        p = fm.polyline_path([QPointF(0, 0), QPointF(10, 0), QPointF(10, 10)])
        self.assertEqual(fm.nodes(p), [0, 1, 2])
        self.assertEqual(fm.move_node(p, 1, 0, -5).boundingRect().getRect(), (0, -5, 10, 15))


class GrupoTest(unittest.TestCase):
    def shapes(self):
        a = ob.Shape(fm.rect_path(QRectF(0, 0, 10, 10)), "a", "C01", "#ffffff")
        b = ob.Shape(fm.ellipse_path(QRectF(20, 0, 10, 20)), "b", "C02", "#ff0000")
        t = ob.TextShape(tx.TextoParams("Oi", "Arial", 5), "t")
        ob.move_by([t], 0, 40)
        return [a, b, t]

    def test_agrupar_preserva_geometria_e_desagrupar_aplica_transformacao(self):
        items = self.shapes()
        before = ob.bounds(items)
        g = ob.group(items)
        self.assertEqual(ob.geom_rect(g), before)
        ob.rotate([g], 90, before.center())
        ob.scale([g], 2, 2, before.center())
        expected = [ob.geom_rect(ob.from_snapshot((c[0], c[1] * g.sceneTransform(), *c[2:]))) for c in g.extra.children]
        parts = ob.ungroup(g)
        self.assertEqual([type(p) for p in parts], [ob.Shape, ob.Shape, ob.TextShape])
        self.assertEqual([p.name for p in parts], ["a", "b", "t"])
        for p, e in zip(parts, expected):
            r = ob.geom_rect(p)
            for x, y in zip(r.getRect(), e.getRect()):
                self.assertAlmostEqual(x, y, delta=1e-9)
        self.assertAlmostEqual(ob.geom_rect(parts[0]).width(), 20, delta=1e-9)  # 10 mm ×2 girado
        self.assertEqual(parts[2].params.texto, "Oi")                           # texto continua editável

    def test_projeto_com_grupo_aninhado(self):
        inner = ob.group(self.shapes()[:2])
        outer = ob.group([inner, self.shapes()[2]])
        ob.rotate([outer], 30, QPointF(0, 0))
        tmp = tempfile.TemporaryDirectory()
        p = os.path.join(tmp.name, "g.rbl")
        pj.save(p, [outer.snapshot()])
        snap = pj.load(p)[0]
        tmp.cleanup()
        restored = ob.from_snapshot(snap)
        self.assertIsInstance(restored, ob.GroupShape)
        self.assertIsInstance(restored.extra.children[0][5], ob.GroupData)
        self.assertEqual(snap, outer.snapshot())

    def test_aninhamento_excessivo_recusado(self):
        o = pj.to_dict([ob.group(self.shapes()[:2]).snapshot()])["objetos"][0]
        for _ in range(pj.MAX_DEPTH + 2):
            o = {**o, "tipo": "grupo", "filhos": [o]}
        with self.assertRaises(pj.ProjetoInvalido):
            pj.from_dict({"formato": pj.FORMAT, "versao": pj.VERSION, "unidade": "mm", "objetos": [o]})
        deep = "[" * 100000 + "]" * 100000
        tmp = tempfile.TemporaryDirectory()
        p = os.path.join(tmp.name, "deep.rbl")
        with open(p, "w") as f:
            f.write(deep)
        with self.assertRaises(pj.ProjetoInvalido):
            pj.load(p)
        tmp.cleanup()


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.win.new_document()
        self.view.zoom_center(2.0)  # 1 px de erro do mouse vira menos mm

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def send(self, kind, scene_pt, button=Qt.LeftButton, buttons=Qt.LeftButton, mods=Qt.NoModifier):
        vp = self.view.viewport()
        pos = self.view.mapFromScene(scene_pt)
        app.sendEvent(vp, QMouseEvent(kind, QPointF(pos), QPointF(vp.mapToGlobal(pos)), button, buttons, mods))
        app.processEvents()
        return self.view.mapToScene(pos)  # posição efetiva (arredondada ao pixel)

    def drag(self, a, b, mods=Qt.NoModifier):
        pa = self.send(QEvent.MouseButtonPress, a, mods=mods)
        self.send(QEvent.MouseMove, (a + b) / 2, Qt.NoButton, Qt.LeftButton, mods)
        pb = self.send(QEvent.MouseMove, b, Qt.NoButton, Qt.LeftButton, mods)
        self.send(QEvent.MouseButtonRelease, b, Qt.LeftButton, Qt.NoButton, mods)
        return pa, pb

    def click(self, pt, mods=Qt.NoModifier):
        p = self.send(QEvent.MouseButtonPress, pt, mods=mods)
        self.send(QEvent.MouseButtonRelease, pt, Qt.LeftButton, Qt.NoButton, mods)
        return p

    def test_retangulo_por_arraste_tem_medida_exata_do_arraste(self):
        self.win.tools["rect"].setChecked(True)
        pa, pb = self.drag(QPointF(100, 100), QPointF(150, 130))
        s = self.view.selected()[0]
        self.assertEqual(s.name, "Retângulo 1")
        self.assertEqual(ob.geom_rect(s), QRectF(pa, pb).normalized())   # exatamente a caixa arrastada
        self.assertTrue(self.win.tools["select"].isChecked())            # volta a Selecionar
        self.assertAlmostEqual(self.win.fields["w"].value(), ob.geom_rect(s).width(), places=2)
        self.assertEqual(self.win.undo_stack.undoText(), "Desenhar retângulo")

    def test_circulo_com_shift_e_ctrl_a_partir_do_centro(self):
        self.win.tools["ellipse"].setChecked(True)
        pa, pb = self.drag(QPointF(100, 100), QPointF(130, 110), Qt.ShiftModifier | Qt.ControlModifier)
        r = ob.geom_rect(self.view.selected()[0])
        side = 2 * max(abs(pb.x() - pa.x()), abs(pb.y() - pa.y()))
        self.assertAlmostEqual(r.width(), side, delta=1e-9)
        self.assertAlmostEqual(r.height(), side, delta=1e-9)
        self.assertAlmostEqual(r.center().x(), pa.x(), delta=1e-9)
        self.assertAlmostEqual(r.center().y(), pa.y(), delta=1e-9)

    def test_poligono_com_lados_da_barra(self):
        self.win.sides.setValue(5)
        self.win.tools["polygon"].setChecked(True)
        pa, pb = self.drag(QPointF(100, 100), QPointF(100, 80))
        s = self.view.selected()[0]
        self.assertEqual(len(fm.nodes(s.path())), 5)
        e = s.path().elementAt(0)
        self.assertAlmostEqual(math.hypot(e.x - pa.x(), e.y - pa.y()), math.hypot(pb.x() - pa.x(), pb.y() - pa.y()))

    def test_clique_sem_arrastar_nao_cria(self):
        self.win.tools["rect"].setChecked(True)
        self.click(QPointF(100, 100))
        self.assertEqual(self.view.shapes(), [])
        self.assertEqual(self.win.undo_stack.count(), 0)

    def test_linhas_aberta_fechada_enter_esc(self):
        self.win.tools["pen"].setChecked(True)
        p1 = self.click(QPointF(100, 100))
        p2 = self.click(QPointF(150, 100))
        p3 = self.click(QPointF(150, 140))
        self.click(QPointF(100, 100))                                # clicar no 1º ponto fecha
        s = self.view.selected()[0]
        self.assertEqual(len(fm.nodes(s.path())), 3)
        self.assertEqual(ob.geom_rect(s), QRectF(p1, p3).normalized())
        last = s.path().elementAt(s.path().elementCount() - 1)
        self.assertEqual((last.x, last.y), (p1.x(), p1.y()))         # fechada
        # aberta com Enter
        self.win.tools["pen"].setChecked(True)
        self.click(QPointF(200, 100))
        self.click(QPointF(250, 120))
        app.sendEvent(self.view, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
        self.assertEqual(len(self.view.shapes()), 2)
        # Esc cancela a linha em andamento
        self.win.tools["pen"].setChecked(True)
        self.click(QPointF(200, 200))
        app.sendEvent(self.view, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        self.click(QPointF(220, 200))
        app.sendEvent(self.view, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        self.assertEqual(len(self.view.shapes()), 2)
        del p2

    def test_linha_shift_45_e_duplo_clique(self):
        self.win.tools["pen"].setChecked(True)
        p1 = self.click(QPointF(100, 100))
        self.click(QPointF(150, 103), Qt.ShiftModifier)
        p = QPointF(150, 160)
        self.send(QEvent.MouseButtonPress, p)
        self.send(QEvent.MouseButtonRelease, p, Qt.LeftButton, Qt.NoButton)
        self.send(QEvent.MouseButtonPress, p)
        self.send(QEvent.MouseButtonDblClick, p)
        self.send(QEvent.MouseButtonRelease, p, Qt.LeftButton, Qt.NoButton)
        s = self.view.selected()[0]
        path = s.path()
        self.assertEqual(len(fm.nodes(path)), 3)                      # o clique duplo não duplicou ponto
        self.assertAlmostEqual(path.elementAt(1).y, p1.y(), delta=1e-9)  # Shift: horizontal exata

    def test_editar_nos_com_mouse_e_desfazer(self):
        self.win.tools["rect"].setChecked(True)
        pa, pb = self.drag(QPointF(100, 100), QPointF(150, 130))
        s = self.view.selected()[0]
        self.win.tools["node"].setChecked(True)
        self.assertEqual(len(self.view.node_overlay.node_points()), 4)
        corner = QPointF(pb)
        self.drag(corner, corner + QPointF(10, 20))
        r = ob.geom_rect(s)
        self.assertAlmostEqual(r.right(), pb.x() + 10, delta=1 / self.view.scale_px_mm)
        self.assertAlmostEqual(r.bottom(), pb.y() + 20, delta=1 / self.view.scale_px_mm)
        self.assertAlmostEqual(r.left(), pa.x(), delta=1e-9)            # outros cantos parados
        self.assertEqual(self.win.undo_stack.undoText(), "Editar nós")
        self.win.undo_stack.undo()
        self.assertEqual(ob.geom_rect(self.view.shapes()[0]), QRectF(pa, pb).normalized())

    def test_nos_nao_aparecem_em_texto_ou_grupo(self):
        self.win.create_text(tx.TextoParams("A", "Arial", 10), QPointF(50, 50))
        self.win.tools["node"].setChecked(True)
        self.assertEqual(self.view.node_overlay.node_points(), [])

    def test_agrupar_desagrupar_na_janela(self):
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 20, 20)), "rect")
        self.win.create_shape(fm.ellipse_path(QRectF(50, 10, 20, 10)), "ellipse")
        self.win.select_all()
        app.processEvents()
        self.assertTrue(self.win.act_group.isEnabled())
        self.win.act_group.trigger()
        self.assertEqual(len(self.view.shapes()), 1)
        g = self.view.shapes()[0]
        self.assertIsInstance(g, ob.GroupShape)
        self.assertEqual(ob.geom_rect(g), QRectF(10, 10, 60, 20))
        self.win.fields["w"].setValue(120)
        self.win.fields["w"].editingFinished.emit()                 # grupo redimensiona como um todo
        self.assertTrue(self.win.act_ungroup.isEnabled())
        self.win.act_ungroup.trigger()
        parts = self.view.shapes()
        self.assertEqual(len(parts), 2)
        self.assertAlmostEqual(ob.geom_rect(parts[0]).width(), 40, delta=1e-9)
        self.assertAlmostEqual(ob.bounds(parts).width(), 120, delta=1e-9)
        self.win.undo_stack.undo()
        self.assertIsInstance(self.view.shapes()[0], ob.GroupShape)


if __name__ == "__main__":
    unittest.main()
