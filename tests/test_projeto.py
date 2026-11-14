"""Etapa 4: alterações reversíveis e projeto recuperado sem perda."""
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
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def same(a, b):
    """Snapshots idênticos: caminho elemento a elemento, matriz, nome, camada e cor."""
    return (pj.path_to_list(a[0]) == pj.path_to_list(b[0]) and a[0].fillRule() == b[0].fillRule()
            and a[1] == b[1] and a[2:] == b[2:])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = self.make()
        self.view = self.win.canvas.view
        self.errors = []

    def make(self):
        w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.show_error = lambda title, text: self.errors.append(text)
        w.resize(1400, 900)
        w.show()
        app.processEvents()
        return w

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def path(self, name="p.rbl"):
        return os.path.join(self.tmp.name, name)

    def snaps(self, win=None):
        return [s.snapshot() for s in (win or self.win).canvas.view.shapes()]

    def shape(self, word):
        return next(s for s in self.view.shapes() if word in s.name)


class ArquivoTest(Base):
    def test_ida_e_volta_sem_perda(self):
        # geometria não trivial: girada, espelhada, escalada; texto com curvas
        rect, ell = self.shape("Retângulo"), self.shape("Elipse")
        ob.rotate([ell], 33.3333, QPointF(1.1, 2.2))
        ob.scale([rect], 1.23456789, 0.987654321, QPointF(0, 0))
        ob.mirror([rect, ell], True)
        before = self.snaps()
        pj.save(self.path(), before)
        after = pj.load(self.path())
        self.assertEqual(len(before), len(after))
        for a, b in zip(before, after):
            self.assertTrue(same(a, b), a[2])
        self.assertFalse(os.path.exists(self.path() + ".tmp"))

    def test_conteudo_versionado_em_mm(self):
        pj.save(self.path(), self.snaps())
        with open(self.path(), encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual((d["formato"], d["versao"], d["unidade"]), ("redblack-laser", pj.VERSION, "mm"))
        self.assertEqual(d["objetos"][0]["nome"], "RedBlack Retângulo")  # acentos preservados

    def test_arquivos_invalidos_sao_rejeitados(self):
        good = pj.to_dict(self.snaps())
        cases = {
            "nao_json": "isto não é json",
            "outro_formato": json.dumps({**good, "formato": "lbrn2"}),
            "versao_nova": json.dumps({**good, "versao": 99}),
            "unidade": json.dumps({**good, "unidade": "in"}),
            "matriz": json.dumps({**good, "objetos": [{**good["objetos"][0], "matriz": [1, 0, 0]}]}),
            "nan": json.dumps({**good, "objetos": [{**good["objetos"][0], "matriz": [float("nan")] * 9}]}),
            "comando": json.dumps({**good, "objetos": [{**good["objetos"][0], "caminho": [["Z"]]}]}),
            "cor": json.dumps({**good, "objetos": [{**good["objetos"][0], "cor": "red"}]}),
        }
        for name, text in cases.items():
            p = self.path(name + ".rbl")
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            with self.assertRaises(pj.ProjetoInvalido, msg=name):
                pj.load(p)

    def test_abrir_invalido_preserva_documento_atual(self):
        before = self.snaps()
        p = self.path("ruim.rbl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("{}")
        self.assertFalse(self.win.open_path(p))
        self.assertEqual(len(self.errors), 1)
        self.assertTrue(all(same(a, b) for a, b in zip(before, self.snaps())))

    def test_salvar_fechar_reabrir(self):
        self.shape("Retângulo").setSelected(True)
        self.win.fields["w"].setValue(123.45)
        self.win.fields["w"].editingFinished.emit()
        before = self.snaps()
        self.assertTrue(self.win.save_to(self.path()))
        self.assertTrue(self.win.undo_stack.isClean())
        self.assertEqual(self.win.windowTitle(), "p.rbl — RedBlack Laser")
        w2 = self.make()
        self.assertTrue(w2.open_path(self.path()))
        after = self.snaps(w2)
        self.assertTrue(all(same(a, b) for a, b in zip(before, after)) and len(before) == len(after))
        r = next(s for s in w2.canvas.view.shapes() if "Retângulo" in s.name)
        self.assertAlmostEqual(ob.geom_rect(r).width(), 123.45, delta=1e-9)
        w2.close()


class HistoricoTest(Base):
    def edit_field(self, key, value):
        self.win.fields[key].setValue(value)
        self.win.fields[key].editingFinished.emit()
        app.processEvents()

    def test_desfazer_refazer_campos(self):
        rect = self.shape("Retângulo")
        rect.setSelected(True)
        app.processEvents()
        original = self.snaps()
        self.edit_field("w", 90)
        self.edit_field("x", 200)
        edited = self.snaps()
        self.assertEqual(self.win.undo_stack.count(), 2)
        self.win.undo_stack.undo()
        self.win.undo_stack.undo()
        self.assertTrue(all(same(a, b) for a, b in zip(original, self.snaps())))
        self.win.undo_stack.redo()
        self.win.undo_stack.redo()
        self.assertTrue(all(same(a, b) for a, b in zip(edited, self.snaps())))

    def test_desfazer_arraste_e_setas(self):
        original = self.snaps()
        a = self.view.mapFromScene(QPointF(70, 40))
        b = self.view.mapFromScene(QPointF(120, 90))
        vp = self.view.viewport()
        for kind, pos, btn, btns in ((QEvent.MouseButtonPress, a, Qt.LeftButton, Qt.LeftButton),
                                     (QEvent.MouseMove, b, Qt.NoButton, Qt.LeftButton),
                                     (QEvent.MouseButtonRelease, b, Qt.LeftButton, Qt.NoButton)):
            app.sendEvent(vp, QMouseEvent(kind, QPointF(pos), QPointF(vp.mapToGlobal(pos)), btn, btns, Qt.NoModifier))
        self.view.nudge(1, 0)
        self.assertEqual([self.win.undo_stack.text(i) for i in range(self.win.undo_stack.count())],
                         ["Mover", "Mover com setas"])
        self.win.undo_stack.setIndex(0)
        self.assertTrue(all(same(a, b) for a, b in zip(original, self.snaps())))

    def test_so_selecionar_nao_entra_no_historico(self):
        a = self.view.mapFromScene(QPointF(70, 40))
        vp = self.view.viewport()
        for kind, btns in ((QEvent.MouseButtonPress, Qt.LeftButton), (QEvent.MouseButtonRelease, Qt.NoButton)):
            app.sendEvent(vp, QMouseEvent(kind, QPointF(a), QPointF(vp.mapToGlobal(a)), Qt.LeftButton, btns, Qt.NoModifier))
        self.assertEqual(self.win.undo_stack.count(), 0)
        self.assertTrue(self.win.undo_stack.isClean())

    def test_desfazer_excluir_e_colar(self):
        names = [s.name for s in self.view.shapes()]
        self.win.select_all()
        self.win.delete()
        self.assertEqual(self.view.shapes(), [])
        self.win.undo_stack.undo()
        self.assertEqual([s.name for s in self.view.shapes()], names)
        self.assertEqual(self.win.obj_tree.topLevelItemCount(), len(names))
        self.assertEqual(len(self.view.selected()), len(names))  # seleção restaurada
        self.win.copy()
        self.win.paste()
        self.assertEqual(len(self.view.shapes()), 2 * len(names))
        self.win.undo_stack.undo()
        self.assertEqual(len(self.view.shapes()), len(names))

    def test_titulo_indica_alteracao_e_ponto_salvo(self):
        self.assertEqual(self.win.windowTitle(), "sem título — RedBlack Laser")
        self.shape("Elipse").setSelected(True)
        self.edit_field("rot", 45)
        self.assertTrue(self.win.windowTitle().startswith("sem título*"))
        self.win.undo_stack.undo()
        self.assertEqual(self.win.windowTitle(), "sem título — RedBlack Laser")

    def test_novo_pergunta_e_cancelar_preserva(self):
        self.shape("Elipse").setSelected(True)
        self.edit_field("rot", 10)
        n = len(self.view.shapes())
        self.win.ask_save = lambda: "cancel"
        self.win.new_document()
        self.assertEqual(len(self.view.shapes()), n)
        self.win.ask_save = lambda: "discard"
        self.win.new_document()
        self.assertEqual(self.view.shapes(), [])
        self.assertEqual(self.win.undo_stack.count(), 0)

    def test_fechar_com_alteracao_cancelado_nao_fecha(self):
        self.shape("Elipse").setSelected(True)
        self.edit_field("rot", 10)
        self.win.ask_save = lambda: "cancel"
        self.assertFalse(self.win.close())
        self.assertTrue(self.win.isVisible())
        self.win.ask_save = lambda: "discard"


if __name__ == "__main__":
    unittest.main()
