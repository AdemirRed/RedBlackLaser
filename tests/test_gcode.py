"""Etapa 11: saída determinística; unidades e limites verificados sem execução física."""
import hashlib
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401  (mesa 400 x 400 dos testes)

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import __version__  # noqa: E402
from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def rect(x, y, w, h, lid="C01"):
    return ob.Shape(fm.rect_path(QRectF(x, y, w, h)), "r", lid, cm.cor(lid)).snapshot()


def layer(lid="C01", **kw):
    return cm.alterar(cm.nova(lid), **kw)


def gerar(snaps, layers, perfil=gc.PERFIL_PADRAO):
    return gc.gerar(pc.gerar(snaps, layers), layers, perfil)


class GeracaoTest(unittest.TestCase):
    def test_retangulo_texto_exato(self):
        """Documento (10,20)–(110,70), Y para baixo -> máquina Y = 400 − y (origem inferior esquerda)."""
        lay = [layer(velocidade_mm_min=600, potencia_max=50, nome="Contorno")]
        got = gerar([rect(10, 20, 100, 50)], lay)
        esperado = f"""; RedBlack Laser {__version__} — G-code GRBL
; Perfil: GRBL genérico (NÃO confirmado na máquina)
; Area de trabalho: 400 x 400 mm; origem inferior esquerda; unidades mm; coordenadas absolutas
; Laser: M3, S 0-1000. EXIGE modo laser do GRBL ($32=1): G0 apaga o feixe.
; Air assist: M8 liga / M9 desliga conforme a camada (sempre M9 no fim).
; ATENCAO: perfil NAO confirmado na maquina. Confira antes de qualquer execucao.
G21 ; milimetros
G90 ; coordenadas absolutas
M5 ; laser desligado
M3 S0 ; modo laser armado com potencia zero
G0 X10.000 Y380.000
; Camada C01 (Contorno): linha, 600 mm/min, 50 %, 1 passada(s)
G1 X110.000 Y380.000 S500 F600
G1 X110.000 Y330.000
G1 X10.000 Y330.000
G1 X10.000 Y380.000
G0 X0.000 Y0.000
M5 ; laser desligado
M2 ; fim do programa
"""
        self.assertEqual(got, esperado)

    def test_deterministico(self):
        snaps = [rect(10, 20, 100, 50), rect(200, 200, 30, 30, "C02")]
        lay = [layer(), layer("C02", modo="preenchimento", intervalo_mm=0.5)]
        a, b = gerar(snaps, lay), gerar(snaps, lay)
        self.assertEqual(hashlib.sha256(a.encode()).hexdigest(), hashlib.sha256(b.encode()).hexdigest())
        self.assertNotIn("-0.000", a)

    def test_unidades_e_somente_comandos_permitidos(self):
        txt = gerar([rect(10, 20, 100, 50)], [layer()])
        cmds = {ln.split(";")[0].split()[0] for ln in txt.splitlines() if ln.split(";")[0].strip()}
        self.assertEqual(cmds, {"G21", "G90", "M5", "M3", "G0", "G1", "M2"})
        codigo = [ln.split()[0] for ln in txt.splitlines() if ln.split(";")[0].strip()]
        self.assertLess(codigo.index("G21"), codigo.index("G0"))
        self.assertLess(codigo.index("G90"), codigo.index("G0"))
        self.assertNotIn("G20", txt)
        self.assertNotIn("G91", txt)

    def test_s_e_f_por_camada_modais_e_m4(self):
        snaps = [rect(0, 0, 10, 10, "C01"), rect(50, 50, 10, 10, "C02")]
        lay = [layer("C01", potencia_max=12.5, velocidade_mm_min=1500, passadas=2),
               layer("C02", potencia_max=100, velocidade_mm_min=300)]
        txt = gerar(snaps, lay, gc.PerfilGrbl(comando="M4", corte_m3=False))  # só M4 (corte em M3 tem teste próprio)
        self.assertIn("M4 S0", txt)
        self.assertNotIn("M3", txt)
        g1 = [ln for ln in txt.splitlines() if ln.startswith("G1")]
        self.assertTrue(g1[0].endswith("S125 F1500"))        # 12,5 % de 1000 = 125
        self.assertEqual(sum("S125" in ln for ln in g1), 1)  # modal: 2ª passada não repete S/F
        self.assertEqual(sum("S1000 F300" in ln for ln in g1), 1)
        self.assertEqual(len(g1), 12)                        # 4 lados × (2 passadas + 1)

    def test_conferencia_relendo_o_gcode(self):
        """O verificador relê o texto: comprimento com laser = percurso; tudo dentro da área; termina apagado."""
        snaps = [rect(10, 20, 100, 50),
                 ob.Shape(fm.ellipse_path(QRectF(200, 100, 60, 60)), "c", "C02", cm.cor("C02")).snapshot()]
        lay = [layer(), layer("C02", modo="preenchimento", intervalo_mm=0.5)]
        perc = pc.gerar(snaps, lay)
        info = gc.analisar(gc.gerar(perc, lay))
        # Coordenadas com 3 casas: até ~0,0007 mm de arredondamento por ponto, somado por segmento.
        tol = 0.0015 * sum(len(t.pontos) for t in perc.trechos)
        self.assertAlmostEqual(info["comprimento_corte"], perc.comprimento_corte, delta=tol)
        self.assertAlmostEqual(info["comprimento_vazio"], perc.comprimento_vazio, delta=tol)
        self.assertLess(tol, 2.0)  # tolerância continua pequena frente a ~6 m de percurso
        self.assertTrue(info["dentro_da_area"])
        self.assertTrue(info["fim_desligado"])
        self.assertEqual(info["s_max"], 200)                 # 20 % padrão
        self.assertEqual(info["x"][0], 0.0)

    def test_curva_tem_comprimento_correto(self):
        s = ob.Shape(fm.ellipse_path(QRectF(100, 100, 40, 40)), "c", "C01", "#fff").snapshot()
        info = gc.analisar(gerar([s], [layer()]))
        self.assertAlmostEqual(info["comprimento_corte"], math.pi * 40, delta=math.pi * 40 * 1e-3)


class LimitesTest(unittest.TestCase):
    def test_fora_da_area_recusado_sem_texto(self):
        for snap in (rect(380, 10, 50, 10), rect(-1, 10, 10, 10), rect(10, -0.5, 10, 10), rect(10, 395, 10, 10)):
            with self.assertRaises(gc.GcodeInvalido) as e:
                gerar([snap], [layer()])
            self.assertIn("fora da área", str(e.exception))

    def test_borda_exata_aceita(self):
        info = gc.analisar(gerar([rect(0, 0, 400, 400)], [layer()]))
        self.assertEqual((info["x"], info["y"]), ((0.0, 400.0), (0.0, 400.0)))

    def test_area_menor_do_perfil(self):
        perfil = gc.PerfilGrbl(largura_mm=300, altura_mm=300)
        with self.assertRaises(gc.GcodeInvalido):
            gerar([rect(250, 10, 100, 10)], [layer()], perfil)  # cabe na mesa demo, não no perfil

    def test_velocidade_acima_do_perfil(self):
        with self.assertRaises(gc.GcodeInvalido) as e:
            gerar([rect(0, 0, 10, 10)], [layer(velocidade_mm_min=30000)])
        self.assertIn("acima do máximo", str(e.exception))

    def test_nada_para_gerar_e_perfil_invalido(self):
        with self.assertRaises(gc.GcodeInvalido):
            gerar([rect(0, 0, 10, 10)], [layer(saida=False)])
        with self.assertRaises(gc.GcodeInvalido):
            gerar([rect(0, 0, 10, 10)], [layer()], gc.PerfilGrbl(comando="M7"))

    def test_verificador_recusa_o_que_nao_deve_existir(self):
        for bad in ("G20\nG90\nG0 X1 Y1\n", "G21\nG91\nG0 X1\n", "G21\nG90\nM3 S100\nG1 X5 Y5\n",
                    "G21\nG90\nG2 X1 Y1 I1 J0\n", "G0 X1 Y1\n"):
            with self.assertRaises(gc.GcodeInvalido, msg=bad):
                gc.analisar(bad)


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(("erro", m))
        self.win.show_info = lambda t, m: self.msgs.append(("info", m))
        self.win.show()
        app.processEvents()
        self.win.new_document()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def test_exportar_grava_o_mesmo_texto(self):
        self.win.create_shape(fm.rect_path(QRectF(10, 20, 100, 50)), "rect")
        p = os.path.join(self.tmp.name, "trabalho.gcode")
        self.assertTrue(self.win.export_gcode_to(p))
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        esperado = gc.gerar(pc.gerar([s.snapshot() for s in self.win.canvas.view.shapes()], self.win.layers),
                            self.win.layers)
        self.assertEqual(txt, esperado)
        self.assertEqual(self.msgs[-1][0], "info")
        self.assertIn("NÃO confirmado", self.msgs[-1][1])
        self.assertFalse(os.path.exists(p + ".tmp"))

    def test_fora_da_area_nao_grava(self):
        self.win.create_shape(fm.rect_path(QRectF(390, 20, 50, 50)), "rect")
        p = os.path.join(self.tmp.name, "x.gcode")
        self.assertFalse(self.win.export_gcode_to(p))
        self.assertFalse(os.path.exists(p))
        self.assertEqual(self.msgs[-1][0], "erro")

    def test_acoes_habilitadas_mas_nada_de_maquina(self):
        self.assertTrue(self.win.act_gcode.isEnabled())
        self.assertTrue(self.win.actions_by_key["export"].isEnabled())
        self.assertNotIn("PySide6.QtSerialPort", sys.modules)


if __name__ == "__main__":
    unittest.main()
