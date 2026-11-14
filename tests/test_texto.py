"""Etapa 7: acentos, alinhamento e fonte ausente tratados; conversão em curvas avaliada."""
import dataclasses
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))  # offscreen não vê fontes do sistema
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
FONT = "Arial" if tx.font_available("Arial") else app.font().family()
MISSING = "Fonte Inexistente RedBlack 123"


def P(texto, **kw):
    return tx.TextoParams(texto, kw.pop("fonte", FONT), **kw)


def box(path):
    return path.boundingRect()


class GeracaoTest(unittest.TestCase):
    def test_altura_e_a_do_x_maiusculo_exata(self):
        for h in (3.0, 10.0, 37.5):
            for bold in (False, True):
                self.assertAlmostEqual(box(tx.build_path(P("X", altura_mm=h, negrito=bold))).height(), h, delta=1e-9)

    def test_acentos_e_cedilha(self):
        h = 10.0
        base, acc = tx.build_path(P("AEIOU", altura_mm=h)), tx.build_path(P("ÁÉÍÓÚ", altura_mm=h))
        self.assertLess(box(acc).top(), box(base).top() - 0.5)          # acento acima da maiúscula
        self.assertGreater(acc.elementCount(), base.elementCount())     # glifos diferentes, não "?"
        c = tx.build_path(P("ç", altura_mm=h))
        self.assertGreater(box(c).bottom(), 0.5)                        # cedilha abaixo da linha de base
        all_pt = tx.build_path(P("ÃÕÂÊÔÀÜ ãõâêôàü çÇ ºª", altura_mm=h))
        self.assertFalse(all_pt.isEmpty())

    def test_alinhamento(self):
        lines = "A\nAAAAAAAA"
        widths = {}
        for al in tx.ALINHAMENTOS:
            p = tx.build_path(P(lines, altura_mm=10, alinhamento=al))
            subs = p.toSubpathPolygons()
            first = [poly.boundingRect() for poly in subs if poly.boundingRect().bottom() <= 0.01]
            second = [poly.boundingRect() for poly in subs if poly.boundingRect().top() > 1]
            l1 = (min(r.left() for r in first), max(r.right() for r in first))
            l2 = (min(r.left() for r in second), max(r.right() for r in second))
            widths[al] = (l1, l2)
        (a1, a2) = widths["esquerda"]
        self.assertAlmostEqual(a1[0], a2[0], delta=0.5)                             # esquerdas iguais
        (c1, c2) = widths["centro"]
        self.assertAlmostEqual(sum(c1) / 2, sum(c2) / 2, delta=0.5)                 # centros iguais
        self.assertAlmostEqual((c1[0] + c1[1]) / 2, 0, delta=0.5)                   # centrado na origem
        (r1, r2) = widths["direita"]
        self.assertAlmostEqual(r1[1], r2[1], delta=0.5)                             # direitas iguais

    def test_entrelinha(self):
        def second_line_top(esp):
            p = tx.build_path(P("X\nX", altura_mm=10, espacamento=esp))
            return max(poly.boundingRect().top() for poly in p.toSubpathPolygons())
        one, two = second_line_top(1.0), second_line_top(2.0)
        self.assertAlmostEqual(two + 10, 2 * (one + 10), delta=1e-6)  # distância entre bases dobra

    def test_fonte_ausente_detectada_e_ainda_desenha(self):
        self.assertTrue(tx.font_available(FONT))
        self.assertTrue(tx.font_available(FONT.upper()))
        self.assertFalse(tx.font_available(MISSING))
        self.assertFalse(tx.build_path(P("Olá", fonte=MISSING)).isEmpty())  # substituta do sistema


class ProjetoTextoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_ida_e_volta_e_fonte_ausente_usa_contorno_salvo(self):
        s = ob.TextShape(P("Faca do João\nCeará", altura_mm=8, negrito=True, alinhamento="centro"), "t")
        ob.rotate([s], 12, QPointF(0, 0))
        p = os.path.join(self.tmp.name, "t.rbl")
        pj.save(p, [s.snapshot()])
        snap = pj.load(p)[0]
        self.assertEqual(snap[5], s.params)
        self.assertEqual(pj.path_to_list(snap[0]), pj.path_to_list(s.path()))
        # Mesmo arquivo com fonte inexistente: abre com o contorno salvo, idêntico.
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        d["objetos"][0]["texto"]["fonte"] = MISSING
        snap2 = pj.from_dict(d)[0]
        restored = ob.from_snapshot(snap2)
        self.assertTrue(restored.fonte_ausente)
        self.assertEqual(pj.path_to_list(restored.path()), pj.path_to_list(s.path()))

    def test_texto_invalido_recusado(self):
        s = ob.TextShape(P("x"), "t")
        d = pj.to_dict([s.snapshot()])
        t = d["objetos"][0]["texto"]
        for bad in ({**t, "alinhamento": "justificado"}, {**t, "altura_mm": -1}, {**t, "negrito": "sim"},
                    {k: v for k, v in t.items() if k != "texto"}, None):
            obj = {**d["objetos"][0], "texto": bad}
            with self.assertRaises(pj.ProjetoInvalido, msg=str(bad)[:50]):
                pj.from_dict({**d, "objetos": [obj]})


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(("erro", m))
        self.win.show_info = lambda t, m: self.msgs.append(("info", m))
        self.answers = []
        self.win.ask_text = lambda initial: (self.answers.append(initial), self.next)[1]
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def click(self, scene_pt, double=False):
        vp = self.view.viewport()
        pos = self.view.mapFromScene(scene_pt)
        kinds = [QEvent.MouseButtonPress, QEvent.MouseButtonRelease]
        if double:
            kinds += [QEvent.MouseButtonDblClick, QEvent.MouseButtonRelease]
        for k in kinds:
            btns = Qt.NoButton if k == QEvent.MouseButtonRelease else Qt.LeftButton
            app.sendEvent(vp, QMouseEvent(k, QPointF(pos), QPointF(vp.mapToGlobal(pos)), Qt.LeftButton, btns, Qt.NoModifier))
        app.processEvents()

    def texts(self):
        return [s for s in self.view.shapes() if isinstance(s, ob.TextShape)]

    def test_ferramenta_texto_cria_no_clique_e_volta_a_selecionar(self):
        self.next = P("Ação", altura_mm=12)
        self.win.tools["text"].setChecked(True)
        self.click(QPointF(100, 200))
        t = self.texts()
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0].name, "Texto “Ação”")
        r = ob.geom_rect(t[0])
        self.assertAlmostEqual(r.left(), 100, delta=3)                 # começa no clique
        self.assertLess(r.bottom(), 200 + 4)                           # sobre a linha de base (ç desce pouco)
        self.assertTrue(self.win.tools["select"].isChecked())
        self.assertFalse(self.view.text_mode)
        self.assertEqual(self.win.undo_stack.undoText(), "Criar texto")

    def test_cancelar_dialogo_nao_cria(self):
        self.next = None
        self.win.tools["text"].setChecked(True)
        self.click(QPointF(100, 200))
        self.assertEqual(self.texts(), [])
        self.assertEqual(self.win.undo_stack.count(), 0)

    def test_duplo_clique_edita_mantendo_posicao_e_desfaz(self):
        self.win.create_text(P("HHHH", altura_mm=20), QPointF(100, 200))
        t = self.texts()[0]
        tf = t.sceneTransform()
        self.next = P("HHHH HHHH", altura_mm=20, negrito=True)
        self.click(QPointF(110, 190), double=True)
        self.assertEqual(self.answers[-1].texto, "HHHH")       # diálogo veio preenchido
        t = self.texts()[0]
        self.assertEqual(t.params.texto, "HHHH HHHH")
        self.assertEqual(t.sceneTransform(), tf)               # posição/rotação mantidas
        self.win.undo_stack.undo()
        self.assertEqual(self.texts()[0].params.texto, "HHHH")

    def test_clique_entre_letras_seleciona_o_texto(self):
        self.win.create_text(P("H   H", altura_mm=20), QPointF(100, 200))
        self.view.scene().clearSelection()
        r = ob.geom_rect(self.texts()[0])
        self.click(r.center())  # espaço vazio entre os dois H
        self.assertEqual(self.view.selected(), self.texts())

    def test_texto_transforma_como_os_outros_objetos(self):
        self.win.create_text(P("Teste", altura_mm=10), QPointF(50, 50))
        f = self.win.fields
        f["w"].setValue(100)
        f["w"].editingFinished.emit()
        self.assertAlmostEqual(ob.geom_rect(self.texts()[0]).width(), 100, delta=1e-9)

    def test_converter_em_curvas_preserva_desenho_e_desfaz(self):
        self.win.create_text(P("Ceará", altura_mm=15), QPointF(50, 100))
        before = ob.geom_rect(self.texts()[0])
        path_before = pj.path_to_list(self.texts()[0].sceneTransform().map(self.texts()[0].path()))
        self.assertTrue(self.win.act_curves.isEnabled())
        self.win.act_curves.trigger()
        self.assertEqual(self.texts(), [])
        curve = self.view.selected()[0]
        self.assertIs(type(curve), ob.Shape)
        self.assertEqual(pj.path_to_list(curve.sceneTransform().map(curve.path())), path_before)
        self.assertEqual(ob.geom_rect(curve), before)
        self.assertFalse(self.win.act_edit_text.isEnabled())
        self.win.undo_stack.undo()
        self.assertEqual(len(self.texts()), 1)

    def test_abrir_projeto_com_fonte_ausente_avisa(self):
        s = ob.TextShape(P("Nome"), "t")
        d = pj.to_dict([s.snapshot()])
        d["objetos"][0]["texto"]["fonte"] = MISSING
        p = os.path.join(self.tmp.name, "f.rbl")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f)
        self.assertTrue(self.win.open_path(p))
        self.assertEqual(self.msgs[0][0], "info")
        self.assertIn(MISSING, self.msgs[0][1])
        t = self.texts()[0]
        self.assertTrue(t.fonte_ausente)
        self.assertEqual(pj.path_to_list(t.path()), pj.path_to_list(s.path()))
        # editar: o diálogo recebe a fonte ausente; usuário escolhe outra e o contorno é refeito
        self.next = dataclasses.replace(t.params, fonte=FONT)
        self.win.edit_text(t)
        self.assertFalse(self.texts()[0].fonte_ausente)


if __name__ == "__main__":
    unittest.main()
