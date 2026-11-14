"""Prévia "peças cortadas em MDF": chapa vira sobra, peças sólidas, furos vazados, linha fraca vira risco."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtGui import QColor, QPolygonF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack.ui import render_mdf as rm  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def ret(x, y, w, h):
    return QPolygonF([QPointF(x, y), QPointF(x + w, y), QPointF(x + w, y + h), QPointF(x, y + h), QPointF(x, y)])


class RenderMdfTest(unittest.TestCase):
    def test_chapa_pecas_e_furos(self):
        chapa, peca, furo, outra = ret(0, 0, 300, 200), ret(10, 10, 120, 80), ret(40, 30, 20, 20), ret(150, 10, 100, 80)
        pecas, sobra = rm.montar_pecas([chapa, peca, furo, outra])
        self.assertEqual(len(pecas), 2)  # a chapa não é peça
        self.assertIsNotNone(sobra)
        com_furo = next(p for p in pecas if p.boundingRect().width() == 120)
        self.assertFalse(com_furo.contains(QPointF(50, 40)))  # furo vazado
        self.assertTrue(com_furo.contains(QPointF(20, 20)))
        # sem chapa: uma peça com furo pequeno continua peça (o furo não vira peça)
        pecas, sobra = rm.montar_pecas([peca, furo])
        self.assertEqual(len(pecas), 1)
        self.assertIsNone(sobra)
        self.assertEqual(len(rm.montar_pecas([peca, furo], externo="chapa")[0]), 1)  # forçado: o furo é a peça

    def test_encadear_pedacos_e_aberturas(self):
        a = QPolygonF([QPointF(0, 0), QPointF(100, 0), QPointF(100, 50)])
        b = QPolygonF([QPointF(100, 50), QPointF(0, 50), QPointF(0, 0)])  # fecha o retângulo com o "a"
        fechados, abertos = rm.encadear([a, b])
        self.assertEqual((len(fechados), len(abertos)), (1, 0))
        c = QPolygonF([QPointF(0, 0), QPointF(100, 0), QPointF(100, 50)])
        d = QPolygonF([QPointF(96, 50), QPointF(0, 50), QPointF(0, 0)])  # abertura de 4 mm
        self.assertEqual(len(rm.encadear([c, d])[0]), 0)  # no rigor: aberto
        fechados, _ = rm.encadear([c, d], rm.ABERTURA_MAX_MM)
        self.assertEqual(len(fechados), 1)
        self.assertAlmostEqual(fechados[0].aberturas[0][0], 4.0, places=6)  # a prévia avisa o tamanho do vão

    def test_janela_renderiza(self):
        w = MainWindow(QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        w.create_shape(fm.rect_path(QRectF(10, 10, 100, 60)), "rect")
        w.create_shape(fm.ellipse_path(QRectF(40, 25, 30, 30)), "ellipse")
        self.assertTrue(w.set_layer_fields("C01", {"potencia_max": 100.0, "velocidade_mm_min": 300.0, "passadas": 2},
                                           "corte"))  # a camada só existe depois do primeiro objeto
        img = rm.renderizar(w)
        self.assertFalse(img.isNull())
        esc = img.width() / (100 + 16)
        madeira = QColor(img.pixel(int((20 - 2) * esc), int((20 - 2) * esc)))
        furo = QColor(img.pixel(int((55 - 2) * esc), int((40 - 2) * esc)))
        self.assertGreater(madeira.red(), 150)  # MDF claro
        self.assertEqual(furo.name(), "#7d8188")  # furo: aparece a mesa (cinza), não a madeira
        prep = rm.preparar_3d(tempfile.mkdtemp(), w, espessura=6.0)  # cena do Blender (sem rodar o Blender)
        self.assertIsNotNone(prep)
        import json
        dados = json.load(open(prep[1], encoding="utf-8"))
        cam = dados["camadas"][0]
        self.assertEqual(cam["espessura"], 6.0)
        self.assertEqual(len(cam["pecas"]), 1)
        self.assertEqual(len(cam["pecas"][0]), 2)  # contorno + 1 furo
        self.assertTrue(os.path.isfile(cam["textura"]))
        self.assertEqual(rm.material_da_aba("Camada rosa", "MDF cru"), "MDF rosa")
        self.assertEqual(rm.material_da_aba("Frente branca + base", "MDF cru"), "MDF branco")
        self.assertEqual(rm.espessura_do_nome("mini-pia-3mm.rbl"), 3.0)
        self.assertEqual(rm.espessura_do_nome("teste 6,5 mm.rbl"), 6.5)
        self.assertEqual(rm.espessura_do_nome("porta.rbl"), 3.0)
        d = w.renderizar_pecas()
        self.assertFalse(d.img.isNull())
        d.definir_zoom(1.0)
        self.assertEqual(d.vista.pixmap().width(), d.pm.width())
        d.zoom_por(1.25)
        self.assertEqual(d.lbl_zoom.text(), "125 %")
        d.ajustar()  # "tirar o zoom": cabe inteira
        self.assertLessEqual(d.vista.pixmap().width(), d.rolagem.viewport().width())
        d.alternar_tela_cheia()
        self.assertIn("Sair", d.b_cheia.text())
        d.alternar_tela_cheia()
        d.close()
        w.close()


if __name__ == "__main__":
    unittest.main()
