import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redblack import geometria as g  # noqa: E402


class GeometriaTest(unittest.TestCase):
    def test_ida_e_volta_exibicao(self):
        for p in ((0, 0), (12.5, 399.9), (-3, 410)):
            self.assertEqual(g.from_display(*g.to_display(*p)), p)
        self.assertEqual(g.to_display(0, g.BED_H), (0, 0))  # origem inferior esquerda

    def test_passos_da_grade(self):
        for scale in (0.2, 0.5, 1, 2.7, 10, 55, 200):
            minor, major = g.steps_for(scale)
            self.assertGreaterEqual(minor * scale, 8 - 1e-9, scale)
            self.assertGreaterEqual(major * scale, 60 - 1e-9, scale)
            self.assertAlmostEqual(major / minor, round(major / minor), msg=scale)  # principal coincide

    def test_ticks_sem_erro_acumulado(self):
        t = g.ticks(-0.25, 1.05, 0.1)
        self.assertEqual(t[0], -0.2)
        self.assertEqual(t[-1], 1.0)
        self.assertIn(0.3, t)  # 3*0.1 != 0.3 em float puro
        self.assertEqual(g.ticks(0, 400, 50), [0, 50, 100, 150, 200, 250, 300, 350, 400])

    def test_distancia_e_escala(self):
        self.assertAlmostEqual(g.distance((0, 0), (30, 40)), 50)
        self.assertEqual(g.clamp_scale(1e6), g.SCALE_MAX)
        self.assertEqual(g.clamp_scale(0), g.SCALE_MIN)

    def test_rotulo(self):
        self.assertEqual(g.fmt_mm(150, 10), "150")
        self.assertEqual(g.fmt_mm(1.5, 0.5), "1,5")


if __name__ == "__main__":
    unittest.main()
