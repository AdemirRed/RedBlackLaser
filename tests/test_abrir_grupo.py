"""Abrir grupo (editar peças sem desagrupar), árvore no painel Objetos, campos ao vivo e réguas na rolagem."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class AbrirGrupoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.show()
        app.processEvents()
        self.w.new_document()
        self.view = self.w.canvas.view
        base = ob.Shape(fm.rect_path(QRectF(100, 100, 200, 100)), "Base", "C01", "#2f6bff")
        furo = ob.Shape(fm.rect_path(QRectF(120, 140, 10, 6)), "Furo", "C02", "#e0313b")
        antes = ob.Shape(fm.rect_path(QRectF(10, 10, 20, 20)), "Antes", "C01", "#2f6bff")
        g = ob.group([furo, base])
        g.name = "P02 Piso"
        self.w._edit("teste", lambda: [self.view.scene().addItem(i) for i in (antes, g)])

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def nomes(self):
        return [s.name for s in self.view.shapes()]

    def grupo(self):
        return next(s for s in self.view.shapes() if isinstance(s, ob.GroupShape))

    def test_abrir_mexer_e_fechar(self):
        self.assertTrue(self.w.abrir_grupo(self.grupo()))
        self.assertEqual(self.nomes(), ["Antes", "Furo", "Base"])  # peças no lugar do grupo
        pai = self.w._grupo_nodes[self.view.shapes()[1].grupo_aberto[0]]
        self.assertEqual(pai.text(0), "📂 P02 Piso")
        self.assertEqual([pai.child(i).text(0) for i in range(pai.childCount())], ["Furo", "Base"])
        furo = self.view.shapes()[1]
        self.view.scene().clearSelection()
        furo.setSelected(True)
        self.w.fields["w"].setValue(20)  # mexe só no furo
        self.w.fields["w"].editingFinished.emit()
        self.assertAlmostEqual(ob.geom_rect(furo).width(), 20, places=6)
        self.assertEqual(self.w.fechar_grupo(), 1)
        self.assertEqual(self.nomes(), ["Antes", "P02 Piso"])  # mesmo nome e mesmo lugar na lista
        filhos = [c[2] for c in self.grupo().extra.children]
        self.assertEqual(filhos, ["Furo", "Base"])
        self.assertTrue(all(s.grupo_aberto is None for s in self.view.shapes()))

    def test_selecionar_o_pai_seleciona_as_pecas_e_desfazer(self):
        self.w.abrir_grupo(self.grupo())
        pai = next(iter(self.w._grupo_nodes.values()))
        pai.setSelected(True)
        app.processEvents()
        self.assertEqual(sorted(s.name for s in self.view.selected()), ["Base", "Furo"])
        self.w.undo_stack.undo()  # desfaz a abertura
        self.assertEqual(self.nomes(), ["Antes", "P02 Piso"])
        self.w.undo_stack.redo()
        self.assertEqual(self.nomes(), ["Antes", "Furo", "Base"])
        self.assertTrue(all(s.grupo_aberto for s in self.view.shapes()[1:]))  # refazer lembra o grupo aberto

    def test_salvar_e_trocar_de_aba_fecham(self):
        self.w.abrir_grupo(self.grupo())
        arq = os.path.join(self.tmp.name, "g.rbl")
        self.assertTrue(self.w.save_to(arq))
        self.assertEqual(self.nomes(), ["Antes", "P02 Piso"])
        with open(arq, encoding="utf-8") as f:
            self.assertEqual([o["nome"] for o in json.load(f)["objetos"]], ["Antes", "P02 Piso"])
        self.w.abrir_grupo(self.grupo())
        self.w.adicionar_pagina()
        self.w.ir_para_pagina(0)
        self.assertEqual(self.nomes(), ["Antes", "P02 Piso"])

    def test_renomear_grupo_fechado_e_aberto(self):
        g = self.grupo()
        node = self.w._tree_map[id(g)][1]
        self.assertEqual(node.childCount(), 2)  # grupo fechado mostra as peças
        self.w.rename_object(g, "Piso da caixa")  # o que o duplo clique na lista (ou F2) faz
        self.assertEqual(self.grupo().name, "Piso da caixa")
        self.w.abrir_grupo(self.grupo())
        gid = self.view.shapes()[1].grupo_aberto[0]
        self.assertTrue(self.w.renomear_grupo_aberto(gid, "Piso P02"))
        self.w.fechar_grupo()
        self.assertEqual(self.grupo().name, "Piso P02")  # o nome novo fica ao fechar

    def test_clicar_peca_de_grupo_fechado_mostra_na_mesa(self):
        g = self.grupo()
        node = self.w._tree_map[id(g)][1]
        furo = node.child(0)
        self.assertEqual(furo.text(0), "Furo")
        furo.setSelected(True)
        app.processEvents()
        self.assertTrue(self.grupo().isSelected())  # o grupo fica selecionado
        r = self.view.destaque.boundingRect()
        self.assertEqual((round(r.x()), round(r.y()), round(r.width()), round(r.height())), (120, 140, 10, 6))
        self.assertTrue(furo.isSelected())  # o item continua marcado na lista
        self.view.scene().clearSelection()
        app.processEvents()
        self.assertIsNone(self.view.destaque)  # selecionar outra coisa tira o destaque

    def test_campo_aplica_sem_enter(self):
        antes = next(s for s in self.view.shapes() if s.name == "Antes")
        self.view.scene().clearSelection()
        antes.setSelected(True)
        app.processEvents()
        self.w.fields["w"].setValue(35)  # como se digitasse, sem Enter
        self.assertAlmostEqual(ob.geom_rect(antes).width(), 20, places=6)
        QTest.qWait(700)
        self.assertAlmostEqual(ob.geom_rect(antes).width(), 35, places=6)

    def test_reguas_acompanham_rolagem(self):
        avisos = []
        self.view.viewChanged.connect(lambda: avisos.append(1))
        self.view.scrollContentsBy(0, 10)
        self.assertTrue(avisos)


if __name__ == "__main__":
    unittest.main()
