"""Disposição automática: nada sobrepõe, respeita vão/margem/mesa/obstáculos, gira quando preciso."""
import itertools
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redblack import disposicao as dp  # noqa: E402


def retangulos(tams, pos):
    out = []
    for (w, h), p in zip(tams, pos):
        if p:
            x, y, g = p
            out.append((x, y, h if g else w, w if g else h))
    return out


def vao(a, b):
    """Maior vão entre dois retângulos (negativo = sobrepõem)."""
    return max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]), b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]))


class DisposicaoTest(unittest.TestCase):
    def conferir(self, tams, pos, W, H, esp, margem, ocupados=()):
        rs = retangulos(tams, pos)
        for r in rs:
            self.assertGreaterEqual(r[0], margem - 1e-6)
            self.assertGreaterEqual(r[1], margem - 1e-6)
            self.assertLessEqual(r[0] + r[2], W - margem + 1e-6)
            self.assertLessEqual(r[1] + r[3], H - margem + 1e-6)
        for a, b in itertools.combinations(rs, 2):
            self.assertGreaterEqual(vao(a, b), esp - 1e-6)
        for r in rs:
            for o in ocupados:
                self.assertGreaterEqual(vao(r, o), esp - 1e-6)

    def test_grade_exata_com_vao(self):
        # 4 × 3 peças de 98 × 63 com vão 2 cabem exatamente em 398 × 195
        tams = [(98, 63)] * 12
        pos = dp.dispor(tams, 398, 195, espaco=2, girar=False)
        self.assertTrue(all(pos))
        self.conferir(tams, pos, 398, 195, 2, 0)

    def test_gira_quando_so_cabe_em_pe(self):
        pos = dp.dispor([(150, 40)], 50, 200, espaco=0)
        self.assertEqual(pos, [(0, 0, True)])
        self.assertEqual(dp.dispor([(150, 40)], 50, 200, espaco=0, girar=False), [None])

    def test_obstaculo_e_margem(self):
        obst = [(0, 0, 100, 100)]
        pos = dp.dispor([(50, 50)] * 3, 200, 200, espaco=5, margem=10, ocupados=obst)
        self.assertTrue(all(pos))
        self.conferir([(50, 50)] * 3, pos, 200, 200, 5, 10, obst)

    def test_aleatorio_nunca_sobrepoe(self):
        rnd = random.Random(7)
        for _ in range(40):
            tams = [(rnd.uniform(5, 120), rnd.uniform(5, 120)) for _ in range(rnd.randint(1, 25))]
            obst = [(rnd.uniform(0, 300), rnd.uniform(0, 300), 40, 30)]
            esp, mg = rnd.choice((0, 1.5, 4)), rnd.choice((0, 3))
            pos = dp.dispor(tams, 400, 400, esp, mg, girar=rnd.random() < 0.5, ocupados=obst)
            self.conferir(tams, pos, 400, 400, esp, mg, obst)

    def test_aproveita_bem(self):
        rnd = random.Random(3)
        tams = [(rnd.uniform(10, 60), rnd.uniform(10, 60)) for _ in range(200)]
        pos = dp.dispor(tams, 400, 400, espaco=0)
        area = sum(w * h for (w, h), p in zip(tams, pos) if p)
        self.assertGreater(area / (400 * 400), 0.8)  # mesa cheia acima de 80 %

    def test_invalidos(self):
        with self.assertRaises(ValueError):
            dp.dispor([(1, 1)], 10, 10, espaco=-1)
        self.assertEqual(dp.dispor([(1, 1)], 10, 10, margem=6), [None])


class DisposicaoJanelaTest(unittest.TestCase):
    def test_comando_arruma_e_desfaz(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import tempfile
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        from redblack import objetos as ob
        from redblack.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"  # sem diálogo modal ao fechar
            antes = sorted(ob.geom_rect(s).getRect() for s in w.canvas.view.shapes())
            self.assertTrue(w.dispor_na_mesa({"espaco": 3.0, "margem": 5.0, "girar": True}))
            rs = [ob.geom_rect(s).getRect() for s in w.canvas.view.shapes()]
            for a, b in itertools.combinations(rs, 2):
                self.assertGreaterEqual(vao(a, b), 3 - 1e-6)
            self.assertTrue(all(r[0] >= 5 - 1e-6 and r[1] >= 5 - 1e-6 for r in rs))
            w.undo_stack.undo()
            self.assertEqual(sorted(ob.geom_rect(s).getRect() for s in w.canvas.view.shapes()), antes)
            w.close()

    def test_reunir_h_e_v(self):
        import tempfile
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        from redblack import objetos as ob
        from redblack.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"  # sem diálogo modal ao fechar
            shapes = w.canvas.view.shapes()
            for s in shapes:
                s.setSelected(True)
            ys = {id(s): ob.geom_rect(s).top() for s in shapes}
            self.assertTrue(w.reunir(True))
            rs = sorted((ob.geom_rect(s) for s in w.canvas.view.shapes()), key=lambda r: r.left())
            for a, b in zip(rs, rs[1:]):
                self.assertAlmostEqual(a.right(), b.left(), places=6)  # encostados, sem vão
            self.assertEqual(sorted(ys.values()), sorted(ob.geom_rect(s).top() for s in w.canvas.view.shapes()))
            for s in w.canvas.view.shapes():
                s.setSelected(True)
            self.assertTrue(w.reunir(False))
            rs = sorted((ob.geom_rect(s) for s in w.canvas.view.shapes()), key=lambda r: r.top())
            for a, b in zip(rs, rs[1:]):
                self.assertAlmostEqual(a.bottom(), b.top(), places=6)
            w.close()


if __name__ == "__main__":
    unittest.main()
