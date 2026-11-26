"""Rotativo (rolo/mandril): conversão de Y no G-code."""
import math
import os
import re
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtGui import QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack import rotativo as rt  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def ys_corte(texto):
    ys, laser = [], False
    for ln in texto.splitlines():
        if ln.startswith("G1") and "Y" in ln:
            ys.append(float(re.search(r"Y(-?[\d.]+)", ln).group(1)))
    return ys


class RotativoTest(unittest.TestCase):
    def test_fator(self):
        rolo = rt.Rotativo(ativo=True, tipo="rolo", mm_por_rotacao=100, diametro_rolo_mm=20, diametro_objeto_mm=80)
        self.assertAlmostEqual(rolo.fator, 100 / (math.pi * 20))             # rolo: diâmetro da peça não entra
        mand = rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=100, diametro_objeto_mm=80)
        self.assertAlmostEqual(mand.fator, 100 / (math.pi * 80))
        self.assertTrue(rt.erros(rt.Rotativo(tipo="x")))
        self.assertEqual(rt.de_dict(rt.para_dict(rolo)), rolo)

    def test_gcode_escala_y_a_partir_do_comeco(self):
        snap = (fm.rect_path(QRectF(10, 300, 20, 50)), QTransform(), "x", "C01", "#fff", None)  # y máq. 50..100
        c = [cm.nova("C01")]
        p = pc.gerar([snap], c)
        normal = ys_corte(gc.gerar(p, c))
        r = rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=360, diametro_objeto_mm=360 / math.pi / 2)  # ×2
        texto = gc.gerar(p, c, rotativo=r)
        rot = ys_corte(texto)
        self.assertAlmostEqual(min(rot), min(normal), 3)                     # começo fica onde está
        self.assertAlmostEqual(max(rot) - min(rot), (max(normal) - min(normal)) * 2, 3)
        self.assertIn("ROTATIVO (mandril)", texto)
        self.assertNotIn("ROTATIVO", gc.gerar(p, c, rotativo=rt.Rotativo()))  # desligado: sem efeito

    def test_janela_lembra_e_exporta(self):
        tmp = tempfile.TemporaryDirectory()
        st = QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat)
        w = MainWindow(st)
        w.ask_save = lambda: "discard"
        w.show_info = lambda *a: None
        w.new_document()
        self.assertFalse(w.rotativo_label.isVisible() and w.rotativo_label.isVisibleTo(w))
        self.assertTrue(w.definir_rotativo(rt.Rotativo(ativo=True, tipo="rolo", mm_por_rotacao=200)))
        self.assertTrue(w.rotativo_label.isVisibleTo(w))
        w.create_shape(fm.rect_path(QRectF(10, 300, 20, 50)), "rect")
        saida = os.path.join(tmp.name, "r.gcode")
        self.assertTrue(w.export_gcode_to(saida))
        with open(saida, encoding="utf-8") as f:
            self.assertIn("ROTATIVO (rolo)", f.read())
        w.close()
        w2 = MainWindow(st)
        self.assertTrue(w2.rotativo.ativo)
        w2.ask_save = lambda: "discard"
        w2.close()
        tmp.cleanup()



class EixoXTest(unittest.TestCase):
    def test_motor_no_x_troca_os_eixos(self):
        r = rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=360, diametro_objeto_mm=360 / (2 * math.pi),
                         eixo="X")
        self.assertEqual(r.fator, 2.0)
        self.assertEqual(rt.de_dict(rt.para_dict(r)).eixo, "X")
        with self.assertRaises(ValueError):
            rt.de_dict({"eixo": "Z"})

class EnquadrarRotativoTest(unittest.TestCase):
    def test_caixa_do_enquadrar_igual_ao_gcode(self):
        from PySide6.QtCore import QRectF
        from redblack import formas as fm
        from redblack.ui.main_window import MainWindow
        d = tempfile.mkdtemp()
        w = MainWindow(QSettings(os.path.join(d, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        w.create_shape(fm.rect_path(QRectF(20, 50, 30, 10)), "rect")
        plano = w.caixa_do_trabalho()
        r = rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=360, diametro_objeto_mm=360 / (2 * math.pi))
        w.definir_rotativo(r)
        caixa = w.caixa_do_trabalho()
        self.assertAlmostEqual(caixa[3] - caixa[1], (plano[3] - plano[1]) * 2, places=6)  # volta ×2
        self.assertAlmostEqual(caixa[2] - caixa[0], plano[2] - plano[0], places=6)
        w.definir_rotativo(rt.Rotativo(**{**rt.para_dict(r), "eixo": "X"}))
        x = w.caixa_do_trabalho()
        self.assertAlmostEqual(x[2] - x[0], (plano[3] - plano[1]) * 2, places=6)  # motor no X: a volta vai no X
        w.definir_rotativo(rt.Rotativo())
        w.close()

    def test_volta_final_so_ate_o_comeco_do_trabalho(self):
        snap = (fm.rect_path(QRectF(10, 30, 20, 50)), QTransform(), "x", "C01", "#fff", None)  # alto na mesa
        c = [cm.nova("C01")]
        p = pc.gerar([snap], c)
        for eixo in ("Y", "X"):
            r = rt.Rotativo(ativo=True, tipo="rolo", mm_por_rotacao=360, diametro_rolo_mm=20, eixo=eixo)  # ×5,7
            texto = gc.gerar(p, c, rotativo=r)
            k = 1 if eixo == "Y" else 0
            giro = [float(v[k]) for v in re.findall(r"X(-?[\d.]+) Y(-?[\d.]+)", texto)]
            ult = [ln for ln in texto.splitlines() if ln.startswith(("G0", "G1"))][-1]
            self.assertIn("volta ao inicio", ult)
            self.assertIn(" S0 ", ult)  # laser apagado
            self.assertGreaterEqual(min(giro), min(giro[1:-1]) - 1e-6)  # nunca gira para trás do começo
            self.assertAlmostEqual(giro[-1], min(giro[1:-1]), 3)         # termina no começo do trabalho

    def test_velocidade_na_superficie_igual_nos_dois_sentidos(self):
        snap = (fm.rect_path(QRectF(10, 30, 20, 20)), QTransform(), "x", "C01", "#fff", None)
        c = [cm.alterar(cm.nova("C01"), velocidade_mm_min=600.0)]
        p = pc.gerar([snap], c)
        antes = gc.PERFIL
        self.addCleanup(setattr, gc, "PERFIL", antes)
        gc.definir_comp_x(0.0, 150.0)  # só o efeito do rotativo
        r = rt.Rotativo(ativo=True, tipo="mandril", mm_por_rotacao=360, diametro_objeto_mm=360 / math.pi / 2,
                        vel_giro_max=20000)  # ×2, sem teto
        g1 = [ln for ln in gc.gerar(p, c, rotativo=r).splitlines() if ln.startswith("G1") and " S0" not in ln]
        fs, f = [], None
        for ln in g1:
            m = re.search(r" F(\d+)", ln)
            f = float(m.group(1)) if m else f
            fs.append(f)
        self.assertEqual(sorted(set(fs)), [600.0, 1200.0])  # lado reto 600, lado em volta 2 × 600 (anda 2× mais)
        self.assertNotIn("F1200", gc.gerar(p, c))           # sem rotativo: tudo 600

    def test_teste_1_volta_completa_e_correcao(self):
        d = tempfile.mkdtemp()
        w = MainWindow(QSettings(os.path.join(d, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.show_error = lambda *a: None
        w.show_info = lambda *a: None
        w.new_document()
        self.assertFalse(w.inserir_teste_rotativo(1))  # rotativo desligado: recusa
        r = rt.Rotativo(ativo=True, tipo="rolo", mm_por_rotacao=300, diametro_rolo_mm=30, diametro_objeto_mm=60)
        w.definir_rotativo(r)
        abas = len(w.paginas)
        self.assertTrue(w.inserir_teste_rotativo(1))
        self.assertEqual(len(w.paginas), abas + 1)
        texto, _cx, _info = w.gcode_do_trabalho()
        ys = sorted({round(float(m), 3) for m in re.findall(r"Y(-?[\d.]+)", texto)})
        c = math.pi * 60
        alvo = c * r.fator  # A e B: exatamente uma volta da peça, já convertida para o eixo
        self.assertTrue(any(abs((b - a) - alvo) < 0.01 for a in ys for b in ys), alvo)
        w.ask_erro_rotativo = lambda: 4.0  # B passou 4 mm
        self.assertTrue(w._corrigir_rotativo_dialogo())
        self.assertAlmostEqual(w.rotativo.mm_por_rotacao, round(300 * c / (c + 4), 3), 3)
        w.ask_erro_rotativo = lambda: 200.0  # mais que meia volta: recusa
        self.assertFalse(w._corrigir_rotativo_dialogo())
        self.assertTrue(w.inserir_teste_rotativo(2))
        self.assertTrue(w.gcode_do_trabalho()[0])
        w.definir_rotativo(rt.Rotativo())
        w.close()

    def test_liberar_grbl_e_girar_uma_volta(self):
        from redblack import conexao as cx
        d = tempfile.mkdtemp()
        w = MainWindow(QSettings(os.path.join(d, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        erros = []
        w.show_error = lambda *a: erros.append(a)
        enviados = []

        class Info:
            v = {20: 1}

            def valor(self, n, padrao=None):
                return self.v.get(n, padrao)

        class Con:
            estado = cx.CONECTADO
            info = Info()

            def limite_software(self, ligado):
                enviados.append(f"$20={int(ligado)}")
                Info.v[20] = int(ligado)

            def jog(self, dx=0.0, dy=0.0, feed=3000.0):
                enviados.append(("jog", dx, dy, feed))
        self.assertFalse(w.girar_uma_volta())  # rotativo desligado
        w.definir_rotativo(rt.Rotativo(ativo=True, mm_por_rotacao=420))
        self.assertFalse(w.girar_uma_volta())  # sem conexão
        w.conexao = Con()
        self.assertFalse(w.girar_uma_volta())  # $20=1: pede para liberar antes
        w.ask_sim = lambda *a: False
        self.assertFalse(w.limite_grbl(False))  # cancelou: nada enviado
        self.assertEqual(enviados, [])
        w.ask_sim = lambda *a: True
        self.assertTrue(w.limite_grbl(False))
        w.ask_voltas = lambda: 1.0
        self.assertTrue(w.girar_uma_volta())
        volta = math.pi * 50 * 420 / (math.pi * 20)  # uma volta da PEÇA (Ø50) num rolo Ø20
        self.assertEqual(enviados[0], "$20=0")
        self.assertEqual(enviados[1][0:2], ("jog", 0.0))
        self.assertAlmostEqual(enviados[1][2], volta, 6)
        self.assertEqual(enviados[1][3], 1000.0)  # velocidade de giro, não a do jog
        self.assertEqual(w.rotativo.mm_por_rotacao, 420)  # deu 1 volta: não muda
        w.show_info = lambda *a: None
        w.ask_voltas = lambda: 5.0  # deu 5 voltas: valor 5× grande demais
        self.assertTrue(w.girar_uma_volta())
        self.assertAlmostEqual(w.rotativo.mm_por_rotacao, 84.0, 3)
        w.definir_rotativo(rt.Rotativo(ativo=True, mm_por_rotacao=420, eixo="X"))
        w.ask_voltas = lambda: None
        self.assertTrue(w.girar_uma_volta())
        self.assertEqual(enviados[-1][0], "jog")
        self.assertAlmostEqual(enviados[-1][1], volta, 6)
        self.assertTrue(w.limite_grbl(True))
        self.assertEqual(enviados[-1], "$20=1")
        w.conexao = None
        w.definir_rotativo(rt.Rotativo())
        w.close()

    def test_giro_nunca_passa_da_velocidade_maxima(self):
        snaps = [(fm.rect_path(QRectF(10, 30, 20, 20)), QTransform(), "a", "C01", "#fff", None),
                 (fm.rect_path(QRectF(60, 120, 20, 20)), QTransform(), "b", "C01", "#fff", None)]
        c = [cm.alterar(cm.nova("C01"), velocidade_mm_min=3000.0)]
        p = pc.gerar(snaps, c)
        antes = gc.PERFIL
        self.addCleanup(setattr, gc, "PERFIL", antes)
        gc.definir_comp_x(0.0, 150.0)
        r = rt.Rotativo(ativo=True, tipo="rolo", mm_por_rotacao=360, diametro_rolo_mm=20, vel_giro_max=800)
        texto = gc.gerar(p, c, rotativo=r)
        self.assertFalse([ln for ln in texto.splitlines() if ln.startswith("G0")])  # nada no máximo do GRBL
        x = y = None
        f = None
        for ln in texto.splitlines():
            if not ln.startswith("G1"):
                continue
            m = re.search(r" F(\d+(\.\d+)?)", ln)
            f = float(m.group(1)) if m else f
            nx, ny = (float(v) for v in re.search(r"X(-?[\d.]+) Y(-?[\d.]+)", ln).groups())
            if x is not None:
                d = math.hypot(nx - x, ny - y)
                if d > 1e-6:
                    self.assertLessEqual(f * abs(ny - y) / d, 800 * 1.01, ln)  # velocidade no eixo que gira
            x, y = nx, ny
        self.assertTrue(gc.analisar(texto)["fim_desligado"])

    def test_referenciar_bloqueado_com_rotativo(self):
        d = tempfile.mkdtemp()
        w = MainWindow(QSettings(os.path.join(d, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        erros = []
        w.show_error = lambda *a: erros.append(a)
        w.definir_rotativo(rt.Rotativo(ativo=True))
        self.assertFalse(w.referenciar_maquina())
        self.assertIn("ROTATIVO", erros[-1][1])
        w.inicio_trabalho.setCurrentIndex(w.inicio_trabalho.findData("origem"))
        self.assertTrue(w._comecar_daqui())  # rotativo: sempre da posição atual
        w.jog_vel.setValue(5000)
        self.assertEqual(w._vel_movimento(), 1000)  # setas/enquadrar limitados ao giro
        w.definir_rotativo(rt.Rotativo())
        self.assertEqual(w._vel_movimento(), 5000)
        self.assertFalse(w._comecar_daqui())  # mesa normal: respeita a escolha
        w.close()

    def test_rotativo_recusa_limite_por_software(self):
        d = tempfile.mkdtemp()
        w = MainWindow(QSettings(os.path.join(d, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        erros = []
        w.show_error = lambda *a: erros.append(a)

        class Info:
            def __init__(self, v):
                self.v = v

            def valor(self, n, padrao=None):
                return self.v.get(n, padrao)

        class Con:
            info = Info({20: 1})

            def fora_do_curso(self, *a):
                return []
        w.conexao = Con()
        w.definir_rotativo(rt.Rotativo(ativo=True))
        self.assertFalse(w._dentro_do_curso((0, 0, 10, 10)))
        self.assertIn("liberar GRBL", erros[-1][1])
        Con.info = Info({20: 0})
        self.assertTrue(w._dentro_do_curso((0, 0, 10, 10)))
        w.definir_rotativo(rt.Rotativo())
        Con.info = Info({20: 1})
        self.assertTrue(w._dentro_do_curso((0, 0, 10, 10)))  # sem rotativo: $20=1 é o normal
        w.conexao = None
        w.close()


if __name__ == "__main__":
    unittest.main()
