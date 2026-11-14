"""Subcamadas: passes extras sobre os mesmos objetos, depois da camada, com os próprios ajustes."""
import json
import os
import sys
import tempfile
import unittest
from dataclasses import asdict

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401  (mesa 400 x 400 e compensação X desligada)

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import percurso as pc  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
SUB_CORTE = (("modo", "linha"), ("velocidade_mm_min", 300.0), ("potencia_max", 90.0))


def quadrado():
    return ob.Shape(fm.rect_path(QRectF(100, 100, 20, 20)), "q", "C01", cm.cor("C01")).snapshot()


class SubcamadasTest(unittest.TestCase):
    def test_expandir(self):
        c = cm.alterar(cm.nova("C01"), modo="preenchimento", subcamadas=(SUB_CORTE,))
        ex = cm.expandir([c, cm.nova("C02")])
        self.assertEqual([x.id for x in ex], ["C01", "C01.1", "C02"])
        v = ex[1]
        self.assertEqual((v.modo, v.velocidade_mm_min, v.potencia_max), ("linha", 300.0, 90.0))
        self.assertEqual(v.intervalo_mm, c.intervalo_mm)  # o resto vem da camada
        self.assertEqual(cm.expandir(ex), ex)  # idempotente
        self.assertEqual(cm.base_id("C01.1"), "C01")

    def test_validacao(self):
        base = cm.nova("C01")
        for ruim in ((("modo", "imagem"),), (("potencia_max", 150.0),), (("cor", "x"),), "nada"):
            with self.assertRaises(ValueError, msg=ruim):
                cm.alterar(base, subcamadas=(ruim,))
        with self.assertRaises(ValueError):
            cm.alterar(cm.nova("C00", imagem=True), subcamadas=(SUB_CORTE,))
        with self.assertRaises(ValueError):
            cm.alterar(base, subcamadas=(SUB_CORTE,) * (cm.MAX_SUB + 1))

    def test_percurso_e_gcode(self):
        c = cm.alterar(cm.nova("C01"), modo="preenchimento", intervalo_mm=1.0, velocidade_mm_min=3000,
                       subcamadas=(SUB_CORTE,))
        p = pc.gerar([quadrado()], [c])
        ordem = [t.camada for t in p.trechos if t.tipo == "corte"]
        self.assertEqual(ordem[-1], "C01.1")  # o contorno vem depois do preenchimento
        self.assertIn("C01", ordem)
        contorno = sum(t.comprimento for t in p.trechos if t.camada == "C01.1" and t.tipo == "corte")
        self.assertAlmostEqual(contorno, 80, places=6)
        txt = gc.gerar(p, [c])
        self.assertIn("; Camada C01.1", txt)
        self.assertIn("S900 F300", txt)  # 90 % de S1000, 300 mm/min
        self.assertTrue(gc.analisar(txt)["fim_desligado"])
        sem_saida = cm.alterar(c, saida=False)
        self.assertEqual(pc.gerar([quadrado()], [sem_saida]).trechos, ())  # a subcamada segue a Saída da camada

    def test_projeto_ida_e_volta(self):
        c = cm.alterar(cm.nova("C01"), subcamadas=(SUB_CORTE, (("passadas", 3),)))
        d = json.loads(json.dumps({"camadas": [asdict(c)]}))  # como vai para o arquivo
        lido, = pj.layers_from_dict(d)
        self.assertEqual(lido, c)
        d["camadas"][0]["subcamadas"] = [[["modo", "imagem"]]]
        with self.assertRaises(pj.ProjetoInvalido):
            pj.layers_from_dict(d)

    def test_painel_adicionar_editar_remover_desfazer(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            lid = w._current_layer_id()
            self.assertTrue(w.subcamada("add", {"modo": "linha", "velocidade_mm_min": 400.0, "potencia_max": 80.0,
                                                "potencia_min": 0.0, "passadas": 2.0, "intervalo_mm": 0.1,
                                                "angulo_graus": 0.0}))
            c = w.layer(lid)
            self.assertEqual(len(c.subcamadas), 1)
            self.assertEqual(w.sub_lista.count(), 1)
            self.assertIn(("passadas", 2), c.subcamadas[0])
            w.sub_lista.setCurrentRow(0)
            v = dict(cm.sub_aplicada(c, c.subcamadas[0]).__dict__)
            self.assertTrue(w.subcamada("edit", {k: v[k] for k in ("modo", "velocidade_mm_min", "potencia_max",
                                                                    "potencia_min", "passadas", "intervalo_mm",
                                                                    "angulo_graus")} | {"velocidade_mm_min": 500.0}))
            self.assertEqual(cm.sub_aplicada(w.layer(lid), w.layer(lid).subcamadas[0]).velocidade_mm_min, 500.0)
            w.sub_lista.setCurrentRow(0)
            self.assertTrue(w.subcamada("del"))
            self.assertEqual(w.layer(lid).subcamadas, ())
            w.undo_stack.undo()
            self.assertEqual(len(w.layer(lid).subcamadas), 1)
            w.close()

    def test_formulario_mostra_campos_da_camada_escolhida(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            t = w.layer_table
            ids = [t.item(r, 0).data(0x0100) for r in range(t.rowCount())]  # Qt.UserRole
            self.assertGreaterEqual(len(ids), 2)
            w.set_layer_fields(ids[0], {"entrada_mm": 3.0, "saida_corte_mm": 1.5}, "teste")
            t.selectRow(1)
            self.assertEqual(w.layer_form["entrada_mm"].value(), w.layer(ids[1]).entrada_mm)
            t.selectRow(0)
            self.assertEqual(w.layer_form["entrada_mm"].value(), 3.0)
            self.assertEqual(w.layer_form["saida_corte_mm"].value(), 1.5)
            w.close()


if __name__ == "__main__":
    unittest.main()
