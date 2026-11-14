"""Giro das peças no gabarito e biblioteca de materiais da S30 Pro Max 20 W — pedidos do usuário."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import gabarito as gbm  # noqa: E402
from redblack import materiais as mt  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.dialogo_gabarito import GabaritoDialog  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
GB = gbm.Gabarito(colunas=2, linhas=1, largura_mm=30, altura_mm=60, espaco_x_mm=5, espaco_y_mm=5,
                  x_mm=20, y_mm=20, giro_graus=90)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat)
        self.win = MainWindow(self.settings)
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(m)
        self.win.show_info = lambda t, m: None
        self.win.new_document()
        self.view = self.win.canvas.view

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()


class GiroTest(Base):
    def test_peca_deitada_cabe_girada_e_fica_centrada(self):
        self.win.create_shape(fm.rect_path(QRectF(100, 200, 50, 20)), "rect")   # 50×20 não cabe em 30×60…
        self.win.select_all()
        self.win.definir_gabarito(GB)
        self.assertTrue(self.win.preencher_gabarito())                            # …girada 90° (20×50) cabe
        for s, (x, y, w, h) in zip(sorted(self.view.shapes(), key=lambda s: s.name), GB.celulas()):
            b = ob.bounds([s])
            self.assertAlmostEqual(b.width(), 20, 6)
            self.assertAlmostEqual(b.height(), 50, 6)
            self.assertAlmostEqual(b.center().x(), x + w / 2, 6)
            self.assertAlmostEqual(b.center().y(), y + h / 2, 6)

    def test_sem_giro_nao_cabe(self):
        self.win.create_shape(fm.rect_path(QRectF(100, 200, 50, 20)), "rect")
        self.win.select_all()
        self.win.definir_gabarito(gbm.Gabarito(**{**gbm.para_dict(GB), "giro_graus": 0.0}))
        self.assertFalse(self.win.preencher_gabarito())
        self.assertEqual(len(self.view.shapes()), 1)

    def test_gabarito_antigo_sem_giro_e_dialogo(self):
        d = gbm.para_dict(GB)
        d.pop("giro_graus")
        self.assertEqual(gbm.de_dict(d).giro_graus, 0.0)                           # projeto v7 anterior
        with self.assertRaises(ValueError):
            gbm.de_dict({**gbm.para_dict(GB), "giro_graus": 500})
        w, h = gbm.caixa_girada(50, 20, 90)
        self.assertAlmostEqual(w, 20)
        self.assertAlmostEqual(h, 50)
        dlg = GabaritoDialog(self.win, GB, self.settings, (50, 20))
        self.assertEqual(dlg.gabarito(), GB)
        dlg._do_tamanho_sel()                                                      # célula do tamanho já girado
        self.assertAlmostEqual(dlg.gabarito().largura_mm, 20)
        self.assertAlmostEqual(dlg.gabarito().altura_mm, 50)


class MateriaisTest(Base):
    def test_referencia_valida_e_marcada(self):
        self.assertTrue(mt.REFERENCIA_S30_PRO_MAX_20W)
        for m in mt.REFERENCIA_S30_PRO_MAX_20W:
            self.assertEqual(mt.erros(m), [], m)
            self.assertEqual(m.origem, "referência")
            self.assertIn("não validado", m.rotulo())
        mdf = next(m for m in mt.REFERENCIA_S30_PRO_MAX_20W if m.nome == "MDF" and m.operacao == "corte")
        self.assertEqual((mdf.espessura_mm, mdf.velocidade_mm_min, mdf.potencia_max, mdf.passadas, mdf.air),
                         (3.6, 300, 100, 1, True))                                # igual à tabela publicada

    def test_aplicar_material_na_camada_e_desfazer(self):
        self.win.layers.append(cm.nova("C01"))
        lid = "C01"
        antes = self.win.layer(lid)
        corte = next(m for m in mt.REFERENCIA_S30_PRO_MAX_20W if m.nome == "Compensado" and m.espessura_mm == 3)
        self.assertTrue(self.win.aplicar_material(corte, lid))
        c = self.win.layer(lid)
        self.assertEqual((c.modo, c.velocidade_mm_min, c.potencia_max, c.passadas, c.air),
                         ("linha", 780, 100, 1, True))
        grav = next(m for m in mt.REFERENCIA_S30_PRO_MAX_20W if m.nome == "MDF" and m.operacao == "gravação")
        self.win.aplicar_material(grav, lid)
        self.assertEqual(self.win.layer(lid).modo, "preenchimento")
        self.win.undo_stack.undo()
        self.win.undo_stack.undo()
        self.assertEqual(self.win.layer(lid), antes)

    def test_camada_de_imagem_so_aceita_gravacao(self):
        img = cm.nova("C05", imagem=True)
        self.win.layers.append(img)
        corte = mt.REFERENCIA_S30_PRO_MAX_20W[0]
        self.assertFalse(self.win.aplicar_material(corte, "C05"))
        grav = next(m for m in mt.REFERENCIA_S30_PRO_MAX_20W if m.operacao == "gravação")
        self.assertTrue(self.win.aplicar_material(grav, "C05"))
        self.assertEqual(self.win.layer("C05").modo, "imagem")

    def test_meus_materiais_salvos_e_excluidos(self):
        self.win.layers.append(cm.nova("C01"))
        lid = "C01"
        self.win.set_layer_fields(lid, {"velocidade_mm_min": 420.0, "potencia_max": 95.0, "air": True}, "x")
        self.assertTrue(self.win.salvar_material(lid, "MDF da loja X", 3))
        self.assertTrue(self.win.salvar_material(lid, "MDF da loja X", 3))       # mesmo nome: substitui
        meus = mt.meus(self.settings)
        self.assertEqual(len(meus), 1)
        self.assertEqual((meus[0].velocidade_mm_min, meus[0].origem), (420.0, "meu"))
        self.assertEqual(self.win.mat_list.item(0).text(), "[Meu] MDF da loja X 3 mm · corte")
        self.assertFalse(self.win.salvar_material(lid, "  ", 3))                  # nome vazio recusado
        self.win.mat_list.setCurrentRow(0)
        self.win._excluir_material()
        self.assertEqual(mt.meus(self.settings), [])
        self.settings.setValue(mt.CHAVE, '[{"nome": 1}]')                         # corrompido: ignorado
        self.assertEqual(mt.meus(self.settings), [])


    def test_mdf_3mm_predefinido_e_editar_material(self):
        mats = self.win.materiais()
        pre = next(m for m in mats if m.nome == "MDF" and m.espessura_mm == 3 and m.operacao == "corte")
        self.assertEqual((pre.potencia_max, pre.passadas), (80, 2))  # predefinição RedBlack
        self.win._montar_materiais(mats.index(pre))
        self.assertFalse(self.win.btn_mat_excluir.isEnabled())  # predefinição não se exclui
        self.win.ask_valores = lambda t, campos, nota="": {**{k: d for k, _r, d, _o in campos},
                                                           "velocidade_mm_min": 450.0, "passadas": 3}
        self.assertTrue(self.win.editar_material(pre))
        novo = next(m for m in self.win.materiais() if m.nome == "MDF" and m.espessura_mm == 3
                    and m.operacao == "corte")
        self.assertEqual((novo.velocidade_mm_min, novo.passadas, novo.potencia_max), (450.0, 3, 80))
        self.assertEqual(sum(1 for m in self.win.materiais() if (m.nome, m.espessura_mm, m.operacao) ==
                             ("MDF", 3, "corte")), 1)  # o seu substitui a predefinição (não duplica)

if __name__ == "__main__":
    unittest.main()
