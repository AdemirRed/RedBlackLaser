"""Compensação do eixo X: desconta mm/min fixos nos cortes em X (gradual nas diagonais), com mínimo; só a
velocidade muda; ligada por padrão e salva; teste SEM × COM."""
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
from redblack.ui import dialogo_calibracao_xy as cxy  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def _sem_f(texto):
    return [re.sub(r" F\d+(\.\d+)?", "", ln) for ln in texto.splitlines() if ln.startswith(("G0", "G1"))]


def _gerar(vel, forma):
    c = cm.Camada("C01", "corte", "linha", vel, 85, 0, 2, 0.1)
    return gc.gerar(pc.gerar([(forma, QTransform(), "f", "C01", "#fff", None)], [c]), [c])


class CompensacaoXTest(unittest.TestCase):
    def test_padrao_no_codigo_e_ligado(self):
        fonte = open(cxy.__file__, encoding="utf-8").read()
        self.assertIn('PADRAO = {"ativo": True, "desconto": 250.0, "minimo": 150.0', fonte)

    def setUp(self):
        self.antes = gc.PERFIL

    def tearDown(self):
        gc.PERFIL = self.antes

    def test_exemplos_minimo_e_geometria(self):
        gc.definir_comp_x(250, 150)
        q = fm.rect_path(QRectF(10, 10, 20, 20))
        for vel, vx in ((800, 550), (1000, 750), (1500, 1250), (300, 150), (120, 120)):
            g = [ln for ln in _gerar(vel, q).splitlines() if ln.startswith("G1")]
            self.assertIn(f"F{vx:g}", g[0], vel)  # 1º lado horizontal (X)
            if vel != vx:
                self.assertIn(f"F{vel:g}", g[1])  # lado vertical (Y): velocidade programada
        self.assertEqual(gc.velocidade_compensada(800, gc.peso_x(1, 1), 250, 150), 675)  # 45°: metade
        circ = _gerar(800, fm.ellipse_path(QRectF(10, 10, 40, 40)))
        fs = sorted(set(float(x) for x in re.findall(r" F(\d+(?:\.\d+)?)", circ)))
        self.assertEqual((fs[0], fs[-1]), (550, 800))
        self.assertTrue(all(b - a <= 13 for a, b in zip(fs, fs[1:])))  # transição gradual (degraus ~12,5)
        gc.definir_comp_x(0, 150)
        sem = _gerar(800, fm.ellipse_path(QRectF(10, 10, 40, 40)))
        self.assertEqual(_sem_f(sem), _sem_f(circ))  # mesmas coordenadas e mesmo S (potência)
        self.assertNotIn("COMPENSACAO", sem)
        with self.assertRaises(ValueError):
            gc.definir_comp_x(250, 0)  # mínimo nunca zero

    def test_ligada_por_padrao_salva_e_desliga(self):
        ativo_antes = cxy.PADRAO["ativo"]
        cxy.PADRAO["ativo"] = True  # o padrão do PROGRAMA (o ambiente de testes desliga para os testes antigos)
        self.addCleanup(cxy.PADRAO.__setitem__, "ativo", ativo_antes)
        s = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.IniFormat)
        w = MainWindow(s)
        self.assertEqual((gc.PERFIL.comp_x_desconto, gc.PERFIL.comp_x_minimo), (250, 150))  # padrão: ligada
        self.assertTrue(w.act_comp_x.isChecked())
        w.act_comp_x.setChecked(False)  # desliga pelo menu
        self.assertEqual(gc.PERFIL.comp_x_desconto, 0)
        w.close()
        w2 = MainWindow(s)  # reabriu: continua desligada (salvo)
        self.assertEqual(gc.PERFIL.comp_x_desconto, 0)
        d = w2.abrir_calibracao_xy()
        d.ativar()
        d.desconto.setValue(200)
        self.assertEqual(gc.PERFIL.comp_x_desconto, 200)
        d.restaurar()
        self.assertEqual(gc.PERFIL.comp_x_desconto, 250)
        texto = cxy.gcode_teste(cxy.ler(s))
        self.assertIn("SEM compensacao: X 800 / Y 800", texto)
        self.assertIn("COM compensacao: X 550 / Y 800", texto)
        self.assertTrue(gc.analisar(texto)["fim_desligado"])
        d.close()
        w2.close()


if __name__ == "__main__":
    unittest.main()
