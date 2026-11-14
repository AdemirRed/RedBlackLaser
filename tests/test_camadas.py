"""Etapa 9: potência, velocidade, passadas, ordem e visibilidade independentes."""
import dataclasses
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class ModeloTest(unittest.TestCase):
    def test_padroes_e_cor(self):
        c = cm.nova("C03")
        self.assertEqual((c.modo, c.passadas, c.saida, c.visivel, c.air), ("linha", 1, True, True, False))
        self.assertEqual(c.cor, cm.PALETA[3])
        self.assertEqual(cm.nova("C00", imagem=True).modo, "imagem")
        self.assertEqual(cm.validar(c), [])
        with self.assertRaises(ValueError):
            cm.nova("C99")

    def test_alterar_valida_e_nao_muta(self):
        c = cm.nova("C01")
        d = cm.alterar(c, potencia_max=55.5, velocidade_mm_min=3000, passadas=3)
        self.assertEqual((c.potencia_max, c.velocidade_mm_min, c.passadas), (20.0, 1000.0, 1))
        self.assertEqual((d.potencia_max, d.velocidade_mm_min, d.passadas), (55.5, 3000, 3))
        for bad in ({"potencia_max": 101}, {"potencia_max": -1}, {"velocidade_mm_min": 0},
                    {"passadas": 0}, {"passadas": 2.5}, {"intervalo_mm": 0}, {"modo": "corte"},
                    {"potencia_min": 30}, {"saida": "sim"}):
            with self.assertRaises(ValueError, msg=str(bad)):
                cm.alterar(c, **bad)  # potencia_min 30 > máx 20


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(m)
        self.win.show_info = lambda t, m: self.msgs.append(m)
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.rect = next(s for s in self.view.shapes() if "Retângulo" in s.name)   # C01
        self.ell = next(s for s in self.view.shapes() if "Elipse" in s.name)       # C02

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def ids(self):
        t = self.win.layer_table
        return [t.item(r, 0).data(Qt.UserRole) for r in range(t.rowCount())]

    def shape(self, word):
        return next(s for s in self.view.shapes() if word in s.name)

    def test_camadas_em_uso_aparecem_na_tabela(self):
        self.assertEqual(self.ids(), ["C01", "C02"])

    def test_parametros_independentes(self):
        w = self.win
        self.assertTrue(w.set_layer_field("C01", "potencia_max", 55))
        self.assertTrue(w.set_layer_field("C01", "velocidade_mm_min", 2500))
        self.assertTrue(w.set_layer_field("C02", "passadas", 4))
        self.assertTrue(w.set_layer_field("C02", "modo", "preenchimento"))
        c1, c2 = w.layer("C01"), w.layer("C02")
        self.assertEqual((c1.potencia_max, c1.velocidade_mm_min, c1.passadas, c1.modo), (55, 2500, 1, "linha"))
        self.assertEqual((c2.potencia_max, c2.velocidade_mm_min, c2.passadas, c2.modo),
                         (20.0, 1000.0, 4, "preenchimento"))
        self.assertEqual(w.undo_stack.count(), 4)
        w.undo_stack.undo()
        self.assertEqual(w.layer("C02").modo, "linha")

    def test_valor_invalido_recusado_sem_alterar(self):
        before = self.win.layer("C01")
        self.assertFalse(self.win.set_layer_field("C01", "potencia_min", 50))  # > máx 20
        self.assertEqual(self.win.layer("C01"), before)
        self.assertEqual(self.win.undo_stack.count(), 0)
        self.assertIn("potência mínima", self.win.statusBar().currentMessage())

    def test_formulario_edita_camada_selecionada(self):
        w = self.win
        w.layer_table.selectRow(1)  # C02
        sb = w.layer_form["velocidade_mm_min"]
        sb.setValue(4321)
        sb.editingFinished.emit()
        self.assertEqual(w.layer("C02").velocidade_mm_min, 4321)
        self.assertEqual(w.layer("C01").velocidade_mm_min, 1000)
        self.assertEqual(w.layer_table.item(1, 5).text(), "4321 / 20 %")

    def test_ordem_e_desfazer(self):
        w = self.win
        w.move_layer("C02", -1)
        self.assertEqual(self.ids(), ["C02", "C01"])
        w.move_layer("C02", -1)  # já está no topo: nada muda
        self.assertEqual(w.undo_stack.count(), 1)
        w.undo_stack.undo()
        self.assertEqual(self.ids(), ["C01", "C02"])

    def test_exibir_independente_de_saida(self):
        w = self.win
        self.ell.setSelected(True)
        w.set_layer_field("C02", "visivel", False)
        ell, rect = self.shape("Elipse"), self.shape("Retângulo")
        self.assertFalse(ell.isVisible())
        self.assertFalse(ell.isSelected())               # oculto sai da seleção
        self.assertTrue(rect.isVisible())
        self.assertTrue(w.layer("C02").saida)            # ocultar não muda a saída
        w.set_layer_field("C01", "saida", False)
        self.assertTrue(self.shape("Retângulo").isVisible())  # desligar saída não oculta
        w.select_all()
        self.assertNotIn(self.shape("Elipse"), self.view.selected())
        w.undo_stack.undo()
        w.undo_stack.undo()
        self.assertTrue(self.shape("Elipse").isVisible())

    def test_checkbox_da_tabela(self):
        t = self.win.layer_table
        t.item(1, 3).setCheckState(Qt.Unchecked)  # Exibir de C02
        self.assertFalse(self.win.layer("C02").visivel)
        t = self.win.layer_table
        t.item(0, 2).setCheckState(Qt.Unchecked)  # Saída de C01
        self.assertFalse(self.win.layer("C01").saida)

    def test_paleta_atribui_camada_e_cor(self):
        w = self.win
        self.rect.setSelected(True)
        w.assign_layer("C03")
        r = self.shape("Retângulo")
        self.assertEqual((r.layer, r.color, r.pen().color().name()), ("C03", cm.PALETA[3], cm.PALETA[3]))
        self.assertEqual(self.ids(), ["C01", "C02", "C03"])   # C01 continua (texto RedBlack)
        self.assertTrue(r.isSelected())
        w.undo_stack.undo()
        self.assertEqual(self.shape("Retângulo").layer, "C01")
        self.assertEqual(self.ids(), ["C01", "C02"])

    def test_grupo_recebe_camada_em_todos_os_filhos(self):
        w = self.win
        self.rect.setSelected(True)
        self.ell.setSelected(True)
        w.group_selected()
        w.assign_layer("C05")
        g = [s for s in self.view.shapes() if isinstance(s, ob.GroupShape)][0]
        self.assertEqual(ob.leaf_layers(g.snapshot()), {"C05"})
        w.ungroup_selected()
        self.assertEqual({s.layer for s in self.view.selected()}, {"C05"})

    def test_ocultar_camada_dentro_de_grupo(self):
        w = self.win
        self.rect.setSelected(True)
        self.ell.setSelected(True)
        w.group_selected()   # filhos C01 e C02
        w.set_layer_field("C02", "visivel", False)
        g = [s for s in self.view.shapes() if isinstance(s, ob.GroupShape)][0]
        self.assertTrue(g.isVisible())   # ainda tem filho visível
        w.set_layer_field("C01", "visivel", False)
        g = [s for s in self.view.shapes() if isinstance(s, ob.GroupShape)][0]
        self.assertFalse(g.isVisible())

    def test_camada_com_imagem_fica_em_modo_imagem(self):
        from test_importar_imagem import png_raw
        p = os.path.join(self.tmp.name, "i.png")
        with open(p, "wb") as f:
            f.write(png_raw(10, 10, (3937, 3937, 1)))
        self.win.import_path(p)
        self.assertEqual(self.win.layer("C00").modo, "imagem")
        self.win.layer_table.selectRow(self.ids().index("C00"))
        self.assertFalse(self.win.layer_form["modo"].isEnabled())
        self.assertTrue(self.win.layer_form["intervalo_mm"].isEnabled())

    def test_projeto_preserva_ordem_e_parametros(self):
        w = self.win
        w.set_layer_field("C02", "potencia_max", 73.5)
        w.set_layer_field("C02", "air", True)
        w.set_layer_field("C01", "nome", "Contorno")
        w.move_layer("C02", -1)
        p = os.path.join(self.tmp.name, "c.rbl")
        self.assertTrue(w.save_to(p))
        expected = list(w.layers)
        w.new_document()
        self.assertTrue(w.open_path(p))
        self.assertEqual(w.layers, expected)
        self.assertEqual(self.ids(), ["C02", "C01"])
        self.assertEqual(w.layer_table.item(1, 1).text(), "Contorno")

    def test_projeto_antigo_ganha_camadas_padrao(self):
        d = pj.to_dict([ob.Shape(fm.rect_path(QRectF(0, 0, 5, 5)), "r", "IMG", "#ffffff").snapshot()])
        d["versao"] = 4
        del d["camadas"]
        p = os.path.join(self.tmp.name, "v4.rbl")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f)
        self.assertTrue(self.win.open_path(p))
        self.assertEqual(self.view.shapes()[0].layer, "C01")      # rótulo antigo migrado
        self.assertEqual(self.ids(), ["C01"])
        self.assertEqual(self.win.layer("C01"), cm.nova("C01"))

    def test_camadas_invalidas_no_arquivo(self):
        good = dataclasses.asdict(cm.nova("C01"))
        base = pj.to_dict([])
        for bad in ([{**good, "id": "X1"}], [{**good, "extra": 1}], [good, good],
                    [{**good, "potencia_min": 90}], [{k: v for k, v in good.items() if k != "air"}], "x"):
            with self.assertRaises(pj.ProjetoInvalido, msg=str(bad)[:60]):
                pj.layers_from_dict({**base, "camadas": bad})


if __name__ == "__main__":
    unittest.main()
