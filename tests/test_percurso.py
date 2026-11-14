"""Etapa 10: movimentos e emissão diferenciados; tempo como estimativa. Valores calculados à mão."""
import math
import os
import sys
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401  (mesa 400 x 400 dos testes)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # helpers de outros módulos de teste

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import geometria as g  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402

app = QApplication.instance() or QApplication([])
O = g.canto_origem()  # (0, 400) com a mesa padrão


def rect(x, y, w, h, layer="C01"):
    s = ob.Shape(fm.rect_path(QRectF(x, y, w, h)), "r", layer, cm.cor(layer))
    return s.snapshot()


def layer(lid="C01", **kw):
    return cm.alterar(cm.nova(lid), **kw)


def run(snaps, layers, **kw):
    return pc.gerar(snaps, layers, **kw)


class LinhaTest(unittest.TestCase):
    def test_retangulo_comprimento_tempo_e_deslocamentos(self):
        p = run([rect(10, 20, 100, 50)], [layer(velocidade_mm_min=600)], rapido=6000)
        self.assertEqual([t.tipo for t in p.trechos], ["vazio", "corte", "vazio"])  # vai, corta, volta
        self.assertAlmostEqual(p.comprimento_corte, 300, delta=1e-9)
        d = math.hypot(10, 400 - 20)                                       # origem -> canto (10, 20)
        self.assertAlmostEqual(p.comprimento_vazio, 2 * d, delta=1e-9)
        self.assertAlmostEqual(p.trechos[1].tempo_s, 300 / (600 / 60), delta=1e-9)   # 30 s
        self.assertAlmostEqual(p.tempo_s, 30 + 2 * d / (6000 / 60), delta=1e-9)
        self.assertEqual(p.trechos[0].pontos, (O, (10.0, 20.0)))
        self.assertEqual(p.trechos[2].pontos[-1], O)

    def test_passadas_repetem_a_camada(self):
        p = run([rect(0, 0, 10, 10)], [layer(passadas=3)])
        self.assertAlmostEqual(p.comprimento_corte, 120, delta=1e-9)
        self.assertEqual([t.tipo for t in p.trechos].count("corte"), 3)
        self.assertEqual(sum(t.tipo == "vazio" for t in p.trechos), 2)    # só ida e volta: contorno fechado

    def test_saida_exibir_e_ordem_das_camadas(self):
        a, b = rect(0, 0, 10, 10, "C01"), rect(50, 0, 10, 10, "C02")
        layers = [layer("C02"), layer("C01")]
        order = [t.camada for t in run([a, b], layers).trechos if t.tipo == "corte"]
        self.assertEqual(order, ["C02", "C01"])                          # ordem da lista, não do documento
        off = [layer("C02", saida=False), layer("C01")]
        self.assertEqual({t.camada for t in run([a, b], off).trechos if t.tipo == "corte"}, {"C01"})
        hidden = [layer("C02", visivel=False), layer("C01")]
        self.assertEqual({t.camada for t in run([a, b], hidden).trechos if t.tipo == "corte"}, {"C01", "C02"})

    def test_velocidade_por_camada_e_vazio_vazio(self):
        p = run([rect(0, 0, 10, 10, "C01"), rect(50, 0, 10, 10, "C02")],
                [layer("C01", velocidade_mm_min=1200), layer("C02", velocidade_mm_min=300)])
        cortes = [t for t in p.trechos if t.tipo == "corte"]
        self.assertAlmostEqual(cortes[0].tempo_s, 40 / 20, delta=1e-9)
        self.assertAlmostEqual(cortes[1].tempo_s, 40 / 5, delta=1e-9)
        res = p.por_camada()
        self.assertEqual(list(res), ["C01", "C02"])
        self.assertAlmostEqual(res["C02"][0], 40, delta=1e-9)

    def test_vazio_ou_sem_objetos(self):
        self.assertEqual(run([], [layer()]).trechos, ())
        self.assertEqual(run([rect(0, 0, 5, 5)], [layer(saida=False)]).tempo_s, 0)
        with self.assertRaises(ValueError):
            run([], [], rapido=0)

    def test_grupo_girado_mantem_comprimento(self):
        grp = ob.group([ob.Shape(fm.rect_path(QRectF(0, 0, 20, 10)), "r", "C01", cm.cor("C01"))])
        ob.rotate([grp], 90, QPointF(0, 0))
        p = run([grp.snapshot()], [layer()])
        self.assertAlmostEqual(p.comprimento_corte, 60, delta=1e-9)
        corte = next(t for t in p.trechos if t.tipo == "corte").pontos
        xs, ys = [q[0] for q in corte], [q[1] for q in corte]
        self.assertAlmostEqual(max(xs) - min(xs), 10, delta=1e-9)   # 20×10 girado 90°: vira 10×20
        self.assertAlmostEqual(max(ys) - min(ys), 20, delta=1e-9)

    def test_circulo_tem_perimetro_exato(self):
        s = ob.Shape(fm.ellipse_path(QRectF(0, 0, 40, 40)), "c", "C01", "#fff")
        p = run([s.snapshot()], [layer()])
        self.assertAlmostEqual(p.comprimento_corte, math.pi * 40, delta=math.pi * 40 * 1e-3)  # < 0,1 %


class PreenchimentoTest(unittest.TestCase):
    def test_retangulo_linhas_sentido_e_comprimento(self):
        p = run([rect(10, 10, 40, 10)], [layer(modo="preenchimento", intervalo_mm=1.0, velocidade_mm_min=3000)])
        cortes = [t for t in p.trechos if t.tipo == "corte"]
        self.assertEqual(len(cortes), 10)
        self.assertAlmostEqual(p.comprimento_corte, 400, delta=1e-9)
        self.assertEqual(cortes[0].pontos, ((10.0, 10.5), (50.0, 10.5)))     # 1ª linha: esquerda -> direita
        self.assertEqual(cortes[1].pontos, ((50.0, 11.5), (10.0, 11.5)))     # 2ª: direita -> esquerda
        ys = [t.pontos[0][1] for t in cortes]
        self.assertEqual([round(b - a, 9) for a, b in zip(ys, ys[1:])], [1.0] * 9)
        vazios_entre = [t for t in p.trechos[2:-1] if t.tipo == "vazio"]
        self.assertTrue(all(abs(t.comprimento - 1.0) < 1e-9 for t in vazios_entre))   # passo de 1 mm

    def test_area_vs_comprimento_do_circulo(self):
        s = ob.Shape(fm.ellipse_path(QRectF(0, 0, 40, 40)), "c", "C01", "#fff")
        p = run([s.snapshot()], [layer(modo="preenchimento", intervalo_mm=0.5)])
        self.assertAlmostEqual(p.comprimento_corte, math.pi * 20 ** 2 / 0.5, delta=math.pi * 400 / 0.5 * 5e-3)

    def test_regra_par_impar_deixa_furo_e_winding_preenche(self):
        def anel(winding):
            path = QPainterPath()
            path.setFillRule(Qt.WindingFill if winding else Qt.OddEvenFill)
            path.addRect(QRectF(0, 0, 40, 40))
            path.addRect(QRectF(10, 10, 20, 20))  # mesmo sentido do externo
            return ob.Shape(path, "a", "C01", "#fff").snapshot()
        lay = [layer(modo="preenchimento", intervalo_mm=1.0)]
        self.assertAlmostEqual(run([anel(False)], lay).comprimento_corte, 1200, delta=1e-9)
        self.assertAlmostEqual(run([anel(True)], lay).comprimento_corte, 1600, delta=1e-9)

    def test_texto_e_imagem_e_forma_minuscula(self):
        from redblack import texto as tx
        t = ob.TextShape(tx.TextoParams("I", "Arial", 10), "t")
        p = run([t.snapshot()], [layer(modo="preenchimento", intervalo_mm=0.2)])
        self.assertGreater(p.comprimento_corte, 10)
        self.assertLess(p.comprimento_corte, 10 * 6 / 0.2)
        from test_importar_imagem import png_raw
        from redblack import importar_imagem as im
        r = im.from_bytes(png_raw(10, 5, (1000, 1000, 1)), "i.png")         # 1000 px/m: 10 × 5 mm
        self.assertAlmostEqual(r.largura_mm, 10, delta=1e-9)
        img = ob.ImageShape(r.imagem, r.largura_mm, r.altura_mm, "i")
        p = run([img.snapshot()], [layer("C00", modo="imagem", intervalo_mm=0.5, modo_imagem="limiar")])
        self.assertAlmostEqual(p.comprimento_corte, 100, delta=1e-6)         # vermelho puro é escuro: 10 × 10 mm
        tiny = rect(0, 0, 5, 0.1)
        p = run([tiny], [layer(modo="preenchimento", intervalo_mm=1.0)])
        self.assertEqual(len([t for t in p.trechos if t.tipo == "corte"]), 1)

    def test_limite_de_linhas_e_desempenho(self):
        big = [rect(0, 0, 400, 400) for _ in range(11)]
        with self.assertRaises(pc.LimiteExcedido) as cm_:
            run(big, [layer(modo="preenchimento", intervalo_mm=0.01)])        # 11 × 40 000 linhas
        self.assertIn("C01", str(cm_.exception))
        t0 = time.perf_counter()
        p = run([rect(0, 0, 400, 400)], [layer(modo="preenchimento", intervalo_mm=0.1)])  # 4 000 linhas
        self.assertLess(time.perf_counter() - t0, 3.0)
        self.assertAlmostEqual(p.comprimento_corte, 4000 * 400, delta=1e-6)


class SimulacaoTest(unittest.TestCase):
    def setUp(self):
        self.p = run([rect(10, 20, 100, 50)], [layer(velocidade_mm_min=600)], rapido=6000)
        self.cron = self.p.cronograma()

    def test_estado_no_meio_do_corte(self):
        t_ida = self.p.trechos[0].tempo_s
        n, pts, atual, emitindo = self.p.estado_em(t_ida + 5, self.cron)        # 5 s de corte = 50 mm
        self.assertEqual(n, 1)
        self.assertTrue(emitindo)
        self.assertAlmostEqual(atual[0], 60, delta=1e-9)                         # 10 + 50
        self.assertAlmostEqual(atual[1], 20, delta=1e-9)
        self.assertEqual(pts[0], (10.0, 20.0))

    def test_estado_no_deslocamento_nos_extremos_e_fim(self):
        n, _, atual, emitindo = self.p.estado_em(0.0, self.cron)
        self.assertEqual((n, emitindo, atual), (0, False, O))
        meio = self.p.trechos[0].tempo_s / 2
        _, _, atual, emitindo = self.p.estado_em(meio, self.cron)
        self.assertFalse(emitindo)
        self.assertAlmostEqual(atual[0], 5, delta=1e-9)
        n, _, atual, _ = self.p.estado_em(1e9, self.cron)                        # além do fim
        self.assertEqual((n, atual), (3, O))
        self.assertEqual(pc.gerar([], []).estado_em(5.0), (0, (), O, False))

    def test_mesa_e_formato_de_tempo(self):
        self.assertFalse(self.p.fora_da_mesa())
        self.assertTrue(run([rect(380, 10, 50, 10)], [layer()]).fora_da_mesa())     # passa de 400 mm
        self.assertTrue(run([rect(-5, 10, 10, 10)], [layer()]).fora_da_mesa())
        self.assertEqual([pc.fmt_tempo(s) for s in (0, 45, 59.6, 125, 3720)], ["0 s", "45 s", "1 min 00 s", "2 min 05 s", "1 h 02 min"])


if __name__ == "__main__":
    unittest.main()
