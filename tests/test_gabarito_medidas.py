"""Gabarito e produção em lote na mesa; valores das medidas na tela — pedidos do usuário."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QLineF, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import gabarito as gbm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack.ui.dialogo_gabarito import GabaritoDialog, salvos  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
AGORA = datetime(2026, 11, 8, 14, 5)
CSV = "Nome\nAna\nBeto\nCaio\nDani\nEva\n".encode("utf-8")  # 5 linhas
GB = gbm.Gabarito(colunas=2, linhas=2, largura_mm=60, altura_mm=30, espaco_x_mm=10, espaco_y_mm=5,
                  x_mm=20, y_mm=20)


class GabaritoTest(unittest.TestCase):
    def test_celulas_em_ordem_de_leitura(self):
        self.assertEqual(GB.celulas(), [(20, 20, 60, 30), (90, 20, 60, 30), (20, 55, 60, 30), (90, 55, 60, 30)])
        self.assertEqual(GB.limites(), (20, 20, 150, 85))
        self.assertEqual(gbm.erros(GB, 400, 400), [])
        self.assertTrue(gbm.erros(gbm.Gabarito(colunas=10, largura_mm=50), 400, 400))  # sai da mesa
        self.assertTrue(gbm.erros(gbm.Gabarito(colunas=0), 400, 400))

    def test_de_dict_recusa_dados_ruins(self):
        self.assertEqual(gbm.de_dict(gbm.para_dict(GB)), GB)
        d = gbm.para_dict(GB)
        for k, v in (("colunas", 1.5), ("colunas", True), ("largura_mm", "60"), ("altura_mm", -1)):
            with self.assertRaises(ValueError):
                gbm.de_dict({**d, k: v})
        with self.assertRaises(ValueError):
            gbm.de_dict({**d, "extra": 1})


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat)
        self.win = MainWindow(self.settings)
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(("erro", m))
        self.win.show_info = lambda t, m: self.msgs.append(("info", m))
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view
        self.win.new_document()
        self.csv = os.path.join(self.tmp.name, "nomes.csv")
        with open(self.csv, "wb") as f:
            f.write(CSV)

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def placa(self):
        """Retângulo 50×20 com texto variável {Nome} dentro, selecionados."""
        self.win.create_shape(fm.rect_path(QRectF(100, 200, 50, 20)), "rect")
        self.win.create_text(tx.TextoParams("{Nome}", "Arial", 8, variavel=True), QPointF(105, 205))
        self.win.select_all()

    def nomes(self):
        out = []
        for s in self.view.shapes():
            filho = next(c for c in s.extra.children if isinstance(c[5], tx.TextoParams))
            out.append((s.name, filho[5].peca, filho[0]))
        return sorted(out)

    def esperado(self, texto):
        return tx.build_path(tx.TextoParams(texto, "Arial", 8))

    def test_preencher_centraliza_e_numera_as_pecas(self):
        self.win.carregar_csv(self.csv)
        self.placa()
        self.assertTrue(self.win.definir_gabarito(GB))
        desl = QRectF(100, 200, 50, 20).center() - ob.bounds(self.win._sel()).center()  # placa × desenho todo
        self.assertTrue(self.win.preencher_gabarito())
        shapes = self.view.shapes()
        self.assertEqual(len(shapes), 4)                                    # original substituído pelas cópias
        for s, (x, y, w, h) in zip(sorted(shapes, key=lambda s: s.name), GB.celulas()):
            ret = next(c for c in s.extra.children if c[5] is None)        # a placa (o nome muda a caixa)
            c = (ret[1] * s.sceneTransform()).map(ret[0]).boundingRect().center() - desl
            self.assertAlmostEqual(c.x(), x + w / 2, 6)                   # desenho centrado na célula
            self.assertAlmostEqual(c.y(), y + h / 2, 6)
        n = self.nomes()
        self.assertEqual([(a, b) for a, b, _ in n], [("Peça 001", 0), ("Peça 002", 1), ("Peça 003", 2), ("Peça 004", 3)])
        self.assertEqual([p for *_, p in n], [self.esperado(t) for t in ("Ana", "Beto", "Caio", "Dani")])
        self.assertEqual(self.win.pecas_por_mesa(), 4)
        self.win.undo_stack.undo()
        self.assertEqual(len(self.view.shapes()), 2)                        # desfaz volta o desenho original

    def test_proxima_mesa_e_pecas_sem_dados_fora_do_gcode(self):
        self.win.carregar_csv(self.csv)
        self.placa()
        self.win.definir_gabarito(GB)
        self.win.preencher_gabarito()
        self.win.avancar_mesa()                                             # linhas 5.. (só Eva)
        self.assertEqual(self.win.vars.linha_atual, 4)
        n = self.nomes()
        self.assertEqual(n[0][2], self.esperado("Eva"))
        self.assertEqual(n[1][2], self.esperado("—"))                        # sem linha: placeholder
        snaps = [s.snapshot() for s in self.view.shapes()]
        self.assertEqual(len(self.win.snaps_saida(snaps, self.win.vars)), 1)  # só a peça com dados
        self.assertIn("3 peça(s)", self.win.vars_panel.lbl_aviso.text())
        self.assertIn("Próxima mesa (4", self.win.vars_panel.btn_avancar.text())
        self.win.avancar_mesa()                                             # planilha acabou: não muda
        self.assertEqual(self.win.vars.linha_atual, 4)

    def test_lote_um_arquivo_por_mesa(self):
        self.win.carregar_csv(self.csv)
        self.placa()
        self.win.definir_gabarito(GB)
        self.win.preencher_gabarito()
        pasta = os.path.join(self.tmp.name, "mesas")
        os.makedirs(pasta)
        feitos = self.win.exportar_lote(pasta, agora=AGORA)
        self.assertEqual([os.path.basename(f) for f in feitos], ["lote_001_Ana.gcode", "lote_002_Eva.gcode"])
        textos = []
        for f in feitos:
            with open(f, encoding="utf-8") as h:
                textos.append(h.read())
        self.assertTrue(all(gc.analisar(t)["dentro_da_area"] for t in textos))
        self.assertGreater(len(textos[0]), len(textos[1]))                  # 2ª mesa só tem 1 peça

    def test_desenho_maior_que_celula_e_recusado(self):
        self.win.create_shape(fm.rect_path(QRectF(100, 200, 80, 20)), "rect")
        self.win.select_all()
        self.win.definir_gabarito(GB)
        self.assertFalse(self.win.preencher_gabarito())
        self.assertEqual(len(self.view.shapes()), 1)
        self.assertEqual(self.msgs[-1][0], "erro")

    def test_gabarito_fora_da_mesa_recusado_e_projeto_guarda(self):
        self.assertFalse(self.win.definir_gabarito(gbm.Gabarito(colunas=20, largura_mm=50)))
        self.assertIsNone(self.win.gabarito)
        self.win.definir_gabarito(GB)
        self.assertTrue(self.view.gabarito_overlay.isVisible())
        p = os.path.join(self.tmp.name, "g.rbl")
        self.win.save_to(p)
        self.win.new_document()
        self.assertIsNone(self.win.gabarito)
        self.assertFalse(self.view.gabarito_overlay.isVisible())
        self.win.open_path(p)
        self.assertEqual(self.win.gabarito, GB)
        self.win.undo_stack.clear()
        self.win.definir_gabarito(None)
        self.win.undo_stack.undo()                                          # remover é desfazível
        self.assertEqual(self.win.gabarito, GB)
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        d["gabarito"]["colunas"] = "2"
        with self.assertRaises(pj.ProjetoInvalido):
            pj.gabarito_from_dict(d)

    def test_editar_texto_mantem_a_peca(self):
        self.placa()
        self.win.definir_gabarito(GB)
        self.win.preencher_gabarito()
        g = sorted(self.view.shapes(), key=lambda s: s.name)[2]
        self.win.canvas.scene.clearSelection()
        g.setSelected(True)
        self.win.ungroup_selected()
        t = next(s for s in self.view.shapes() if isinstance(s, ob.TextShape))
        self.win.ask_text = lambda initial: tx.TextoParams("{n}", "Arial", 8, variavel=True)
        self.win.edit_text(t)
        t = next(s for s in self.view.shapes() if isinstance(s, ob.TextShape))
        self.assertEqual(t.params.peca, 2)
        self.assertEqual(t.path(), self.esperado("3"))                       # contador 1 + 2 peças

    def test_dialogo_salva_gabaritos_para_reutilizar(self):
        dlg = GabaritoDialog(self.win, GB, self.settings, (55, 25))
        self.assertEqual(dlg.gabarito(), GB)                                 # X/Y convertidos ida e volta
        dlg.pedir_nome = lambda: "Chaveiros MDF"
        dlg._salvar()
        self.assertEqual(salvos(self.settings), {"Chaveiros MDF": GB})
        dlg._do_tamanho_sel()
        self.assertEqual((dlg.gabarito().largura_mm, dlg.gabarito().altura_mm), (55, 25))
        dlg.campos["colunas"].setValue(30)
        from PySide6.QtWidgets import QDialogButtonBox
        self.assertFalse(dlg.botoes.button(QDialogButtonBox.Ok).isEnabled())  # fora da mesa
        dlg.combo.setCurrentText("Chaveiros MDF")
        dlg._carregar_salvo()
        self.assertEqual(dlg.gabarito(), GB)
        self.settings.setValue("gabaritos", "{corrompido")
        self.assertEqual(salvos(self.settings), {})

    # ---------- medidas na tela ----------
    def test_medir_mostra_valor_em_cima_da_linha(self):
        self.win.tools["measure"].setChecked(True)
        vp = self.view.viewport()
        a = self.view.mapFromScene(QPointF(10, 100))
        b = self.view.mapFromScene(QPointF(110, 100))
        QTest.mousePress(vp, Qt.LeftButton, Qt.AltModifier, a)               # Alt: sem encaixe
        QTest.mouseMove(vp, b)
        QTest.mouseRelease(vp, Qt.LeftButton, Qt.AltModifier, b)
        med = self.view.medidas
        linha = med.itens["medida"]
        self.assertIsInstance(linha, QLineF)
        self.assertEqual(len(med.textos()), 1)
        self.assertAlmostEqual(linha.length(), 100, delta=2 / self.view.scale_px_mm)
        self.view.grab()                                                     # pinta sem erro
        self.win.act_medidas.setChecked(False)                               # a régua mostra mesmo assim
        self.assertEqual(len(med.textos()), 1)
        self.assertFalse(self.settings.value("mostrar_medidas", True, type=bool))
        self.win.act_medidas.setChecked(True)
        self.win.tools["select"].setChecked(True)
        self.assertNotIn("medida", med.itens)

    def test_selecao_e_forma_em_desenho_mostram_largura_e_altura(self):
        self.win.create_shape(fm.rect_path(QRectF(10, 10, 40, 25)), "rect")
        self.assertEqual(self.view.medidas.textos()[:2], ["40,00 mm", "25,00 mm"])  # depois vêm as distâncias aos lados
        self.view.scene().clearSelection()
        self.assertEqual(self.view.medidas.textos(), [])
        self.win.tools["rect"].setChecked(True)
        vp = self.view.viewport()
        a, b = self.view.mapFromScene(QPointF(200, 200)), self.view.mapFromScene(QPointF(260, 230))
        QTest.mousePress(vp, Qt.LeftButton, Qt.AltModifier, a)
        QTest.mouseMove(vp, b)
        self.assertIn("previa", self.view.medidas.itens)
        QTest.mouseRelease(vp, Qt.LeftButton, Qt.AltModifier, b)
        self.assertNotIn("previa", self.view.medidas.itens)

    def test_opcao_medidas_lembrada(self):
        self.win.act_medidas.setChecked(False)
        self.win.close()
        w2 = MainWindow(self.settings)
        self.assertFalse(w2.act_medidas.isChecked())
        self.assertFalse(w2.canvas.view.medidas.ativo)
        w2.ask_save = lambda: "discard"
        w2.close()


if __name__ == "__main__":
    unittest.main()
