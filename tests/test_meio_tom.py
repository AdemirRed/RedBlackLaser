"""Meio-tom: a fração gravada acompanha o tom; branco nunca grava; células e ângulo mudam o padrão."""
import math
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redblack import camadas as cm  # noqa: E402
from redblack import raster as rs  # noqa: E402


def cobertura(tom, n=100, cpi=50.0, ang=45.0, passo=0.1):
    linhas = [[tom] * n for _ in range(n)]
    pot = rs.potencias(linhas, "meio_tom", 50, 0, 80, (cpi, ang, passo))
    return sum(v > 0 for lin in pot for v in lin) / n / n, pot


class MeioTomTest(unittest.TestCase):
    def test_area_do_disco(self):
        self.assertAlmostEqual(rs._area_disco(0.0), 0.0)
        self.assertAlmostEqual(rs._area_disco(0.25), math.pi / 4)
        self.assertAlmostEqual(rs._area_disco(0.5), 1.0)
        vals = [rs._area_disco(i / 200) for i in range(101)]
        self.assertEqual(vals, sorted(vals))  # cresce sem saltos para trás

    def test_fracao_acompanha_o_tom(self):
        self.assertEqual(cobertura(255)[0], 0.0)  # branco nunca grava
        self.assertGreater(cobertura(0)[0], 0.97)  # preto quase todo
        for tom in (64, 128, 192):
            f, pot = cobertura(tom)
            self.assertAlmostEqual(f, 1 - tom / 255, delta=0.06, msg=tom)
            self.assertEqual({v for lin in pot for v in lin} - {0}, {80})  # liga na potência máxima

    def test_celulas_e_angulo_mudam_o_padrao(self):
        _, a = cobertura(128)
        _, b = cobertura(128, ang=0.0)
        _, c = cobertura(128, cpi=20.0)
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        # 20 cpi com passo 0,1 mm: célula de 12,7 pontos; num trecho de 100 pontos na linha cabem ~8 pontos
        meio = c[6]
        trechos = sum(1 for i in range(1, len(meio)) if meio[i] and not meio[i - 1])
        self.assertTrue(5 <= trechos <= 10, trechos)

    def test_camada_valida_e_limites(self):
        c = cm.alterar(cm.nova("C01", imagem=True), modo_imagem="meio_tom", meio_tom_cpi=80, meio_tom_angulo=-30)
        self.assertEqual(c.modo_imagem, "meio_tom")
        with self.assertRaises(ValueError):
            cm.alterar(c, meio_tom_cpi=1)


if __name__ == "__main__":
    unittest.main()
