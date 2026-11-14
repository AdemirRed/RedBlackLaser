"""Ângulo de varredura, bidirecional, hachura cruzada e sobrevarredura da camada."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack import projeto as pj  # noqa: E402

app = QApplication.instance() or QApplication([])


def snap(r):
    return (fm.rect_path(QRectF(*r)), QTransform(), "x", "C01", "#fff", None)


def camada(**kw):
    return cm.alterar(cm.nova("C01"), modo="preenchimento", intervalo_mm=1.0, **kw)


def cortes(p):
    return [t for t in p.trechos if t.tipo == "corte"]


class VarreduraTest(unittest.TestCase):
    def test_angulo_90_faz_linhas_verticais(self):
        p = pc.gerar([snap((10, 10, 20, 5))], [camada(angulo_graus=90)])
        cs = cortes(p)
        self.assertEqual(len(cs), 20)                                        # 20 mm / 1 mm
        for t in cs:
            (x0, y0), (x1, y1) = t.pontos
            self.assertAlmostEqual(x0, x1, 6)                               # vertical
            self.assertAlmostEqual(abs(y1 - y0), 5, 6)

    def test_bidirecional_desligado(self):
        p = pc.gerar([snap((0, 0, 10, 4))], [camada(bidirecional=False)])
        self.assertTrue(all(t.pontos[1][0] > t.pontos[0][0] for t in cortes(p)))  # sempre da esquerda p/ direita
        q = pc.gerar([snap((0, 0, 10, 4))], [camada()])
        self.assertEqual(sum(t.pontos[1][0] < t.pontos[0][0] for t in cortes(q)), 2)  # ida e volta

    def test_hachura_cruzada_e_incremento(self):
        p = pc.gerar([snap((0, 0, 10, 4))], [camada(hachura_cruzada=True)])
        self.assertEqual(len(cortes(p)), 4 + 10)
        q = pc.gerar([snap((0, 0, 10, 10))], [camada(passadas=2, angulo_inc_graus=90)])
        horiz = sum(abs(t.pontos[0][1] - t.pontos[1][1]) < 1e-9 for t in cortes(q))
        self.assertEqual((horiz, len(cortes(q)) - horiz), (10, 10))         # 1ª passada 0°, 2ª passada 90°

    def test_sobrevarredura_no_percurso_e_gcode(self):
        p = pc.gerar([snap((50, 50, 10, 2))], [camada(sobrevarredura_mm=3, velocidade_mm_min=1200)])
        sobras = [t for t in p.trechos if t.tipo == "sobra"]
        self.assertEqual(len(sobras), 4)                                    # antes e depois de cada linha
        self.assertTrue(all(abs(t.comprimento - 3) < 1e-9 and t.velocidade == 1200 for t in sobras))
        self.assertAlmostEqual(p.comprimento_corte, 20, 6)                  # o corte não muda
        texto = gc.gerar(p, [camada(sobrevarredura_mm=3, velocidade_mm_min=1200)])
        self.assertEqual(texto.count(" S0"), 4 + 1)                         # 4 sobras + armar com S0
        self.assertTrue(gc.analisar(texto)["fim_desligado"])
        self.assertAlmostEqual(gc.analisar(texto)["comprimento_corte"], 20, 3)

    def test_projeto_antigo_recebe_padrao(self):
        d = pj.to_dict([], [cm.Camada("C01", "c", angulo_graus=45, sobrevarredura_mm=2)])
        self.assertEqual(pj.layers_from_dict(d)[0].angulo_graus, 45)
        for k in ("angulo_graus", "angulo_inc_graus", "bidirecional", "hachura_cruzada", "sobrevarredura_mm",
                  "kerf_mm"):
            del d["camadas"][0][k]
        c = pj.layers_from_dict(d)[0]
        self.assertEqual((c.angulo_graus, c.bidirecional, c.sobrevarredura_mm), (0.0, True, 0.0))
        d["camadas"][0]["bidirecional"] = "sim"
        with self.assertRaises(pj.ProjetoInvalido):
            pj.layers_from_dict(d)


if __name__ == "__main__":
    unittest.main()
