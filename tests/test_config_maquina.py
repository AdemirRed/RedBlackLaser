"""Configurações da máquina: mesa, canto da origem e perfil do G-code; botões das barras."""
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
from redblack import gcode as gc  # noqa: E402
from redblack import geometria as g  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
MESA = {"largura": 300.0, "altura": 200.0, "origem": "sup_dir", "comando": "M4", "s_max": 255, "f_max": 6000.0}


def gerar_quadrado(x, y, lado=10):
    snap = ob.Shape(fm.rect_path(QRectF(x, y, lado, lado)), "r", "C01", cm.cor("C01")).snapshot()
    lay = [cm.alterar(cm.nova("C01"), velocidade_mm_min=1000)]
    return gc.gerar(pc.gerar([snap], lay), lay)


class ConfigMaquinaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat)

    def tearDown(self):
        g.definir_mesa(400.0, 400.0, "inf_esq")  # estado global: não vazar para outros testes
        gc.definir_perfil()
        self.tmp.cleanup()

    def test_origem_e_perfil_no_gcode(self):
        g.definir_mesa(300, 200, "sup_dir")
        gc.definir_perfil("M4", 255, 6000)
        txt = gerar_quadrado(0, 0)  # canto superior esquerdo do documento
        self.assertIn("300 x 200 mm; origem superior direita", txt)
        self.assertIn("M4 S0", txt)
        info = gc.analisar(txt)
        # origem sup. dir.: x da máquina = 300 - x; y = y do documento
        self.assertEqual(info["x"], (0.0, 300.0))  # inclui o ponto de partida (0, 0) da máquina
        self.assertEqual(info["y"], (0.0, 10.0))
        g1 = {tuple(float(w[1:]) for w in ln.split()[1:3]) for ln in txt.splitlines() if ln.startswith("G1 ")}
        self.assertEqual({x for x, _ in g1} | {y for _, y in g1}, {290.0, 300.0, 0.0, 10.0})
        self.assertTrue(info["dentro_da_area"])
        self.assertIn(" S51 ", txt)  # camada a 20 %: round(0,2 × 255) no S máximo do perfil
        self.assertEqual(pc.gerar([], []).inicio, (300.0, 0.0))  # o percurso parte da origem

    def test_fora_da_mesa_menor_recusa(self):
        g.definir_mesa(100, 100)
        with self.assertRaises(gc.GcodeInvalido):
            gerar_quadrado(150, 10)

    def test_valores_invalidos_recusados(self):
        for args in ((5, 100), (100, 6000), (100, 100, "meio")):
            with self.assertRaises(ValueError):
                g.definir_mesa(*args)
        for args in (("M7", 1000, 100), ("M3", 0, 100), ("M3", 1000, 0)):
            with self.assertRaises(ValueError):
                gc.definir_perfil(*args)

    def test_dialogo_aplica_lembra_e_redesenha(self):
        w = MainWindow(self.settings)
        w.ask_valores = lambda *a, **k: dict(MESA)
        w.act_maquina.trigger()
        self.assertEqual((g.BED_W, g.BED_H, g.ORIGEM), (300.0, 200.0, "sup_dir"))
        self.assertEqual((gc.PERFIL.comando, gc.PERFIL.s_max), ("M4", 255))
        self.assertIn("300 × 200", w.mesa_label.text())
        borda = [i for i in w.canvas.scene.items() if i.data(0x5ED) and hasattr(i, "rect")
                 and i.rect() == QRectF(0, 0, 300, 200)]
        self.assertEqual(len(borda), 1)  # mesa redesenhada, sem duplicar
        w.close()
        g.definir_mesa(400, 400)
        w2 = MainWindow(self.settings)  # reabrir: lido das configurações
        self.assertEqual((g.BED_W, g.BED_H, g.ORIGEM, gc.PERFIL.comando), (300.0, 200.0, "sup_dir", "M4"))
        w2.close()

    def test_config_corrompida_volta_ao_padrao(self):
        self.settings.setValue("maquina", '{"largura": -1}')
        w = MainWindow(self.settings)
        self.assertEqual((g.BED_W, g.BED_H, gc.PERFIL.comando), (400.0, 400.0, "M3"))
        w.close()

    def test_botoes_nas_barras(self):
        w = MainWindow(self.settings)
        agrupadas = {a.text().replace("&", "") for _t, acoes in w.grupos_barra for a in acoes}
        principal = {a.text().replace("&", "") for a in w.barra_principal.actions()} | agrupadas
        for t in ("Mover a vista", "Agrupar", "Desagrupar / separar", "Espelhar na horizontal",
                  "Alinhar à esquerda", "Distribuir na vertical", "Configurações da máquina…"):
            self.assertIn(t, principal)
        ferr = {a.text().replace("&", "") for a in w.barra_ferramentas.actions()} | agrupadas
        for t in ("Deslocar formas…", "União booleana", "Matriz em grade…", "Matriz circular…"):
            self.assertIn(t, ferr)
        from PySide6.QtWidgets import QWidgetAction
        for a in w.barra_principal.actions() + w.barra_ferramentas.actions():
            if isinstance(a, QWidgetAction):
                continue  # campo (ex.: raio do Bolear), não botão
            self.assertTrue(a.isSeparator() or not a.icon().isNull(), a.text())
        w.tools["pan"].trigger()
        self.assertTrue(w.canvas.view.modo_mao)
        w.tools["select"].trigger()
        self.assertFalse(w.canvas.view.modo_mao)
        w.close()


if __name__ == "__main__":
    unittest.main()
