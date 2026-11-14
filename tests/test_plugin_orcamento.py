"""Tempo estimado acima das camadas (aba e projeto) e plugin Orçamento (tempo × R$ 30/h)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack.plugins import orcamento as orc  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class OrcamentoTest(unittest.TestCase):
    def test_conta(self):
        r = orc.calcular(30 * 60, 30.0, material=5, outros=2, margem_pct=50, quantidade=2)
        self.assertAlmostEqual(r["maquina"], 30.0)  # 2 × 30 min a R$ 30/h
        self.assertAlmostEqual(r["custo"], 44.0)
        self.assertAlmostEqual(r["total"], 66.0)
        self.assertAlmostEqual(r["por_peca"], 33.0)
        self.assertEqual(orc.reais(1234.5), "R$ 1.234,50")
        with self.assertRaises(ValueError):
            orc.calcular(-1, 30)

    def test_custo_preco_lucro_tres_camadas(self):
        r = orc.orcar(dict(orc.MODELOS_INICIAIS["Tyfani"]))  # dados do levantamento (chapa R$ 44, 35 placas…)
        self.assertAlmostEqual(r["mdf"], 3.77)           # 3 placas de R$ 1,2571, não 1 chapa por peça
        self.assertEqual(r["pecas_por_chapa"], 11)        # 35 placas = 11 porta-retratos completos (3 camadas)
        self.assertEqual(r["sobra_placas"], 2)
        self.assertAlmostEqual(r["tinta"], 1.53)          # R$ 46 / 900 ml × 30 ml
        self.assertAlmostEqual(r["cola"], 1.11)           # R$ 39 / 35 peças
        self.assertAlmostEqual(r["remun_maquina"], 29.17)  # 35 min × R$ 50/h
        self.assertAlmostEqual(r["manual"], 2.50)         # 10 min × R$ 15/h
        self.assertAlmostEqual(r["custo"], 38.09)
        self.assertAlmostEqual(r["preco"], 60.0)
        self.assertAlmostEqual(r["lucro"], 21.91)
        self.assertAlmostEqual(r["desembolso"], 6.42)     # dinheiro que sai de fato
        t = orc.tabela_descontos(dict(orc.MODELOS_INICIAIS["Valentina Hellena"]))
        self.assertEqual([x[0] for x in t], [1, 5, 10, 20])
        self.assertAlmostEqual(t[3][2], 42.5)              # 15 % de desconto em 20+
        self.assertTrue(orc.dicas(r, orc.MODELOS_INICIAIS["Tyfani"] | {k: d for k, (_, d, _t) in orc.CAMPOS.items()
                                                                          if k not in orc.MODELOS_INICIAIS["Tyfani"]}))
        with self.assertRaises(ValueError):
            orc.orcar({"camadas": 0})

    def test_tempo_das_abas_e_janela(self):
        d = tempfile.mkdtemp()
        w = MainWindow(QSettings(os.path.join(d, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        w.create_shape(fm.rect_path(QRectF(10, 10, 100, 50)), "rect")
        w.adicionar_pagina(False)
        w.create_shape(fm.rect_path(QRectF(10, 10, 100, 50)), "rect")
        w._calcular_tempo(em_segundo_plano=False)
        t = w.tempos_estimados
        self.assertEqual(len(t["por_aba"]), 2)
        self.assertGreater(t["aba"], 0)
        self.assertAlmostEqual(t["total"], sum(t["por_aba"]), places=6)
        self.assertIn("Projeto (2 abas)", w.tempo_label.text())
        self.assertIn("orcamento", [a for a in ("orcamento",) if hasattr(w, "plugin_orcamento")])
        j = w.plugin_orcamento["abrir"]()
        self.assertAlmostEqual(j.valor_hora.value(), 50.0)  # referência de preço do levantamento
        self.assertEqual(j.origem.currentData(), "total")  # puxa do plano aberto por padrão
        self.assertAlmostEqual(j.minutos.value(), t["total"] / 60, places=1)
        self.assertEqual(j.abas.count(), 2)  # Orçamento + Configurações
        self.assertEqual(j.tabela.item(0, 0).text(), "MDF")
        j.campos["quantidade"].setValue(10)  # faixa de 10 % de desconto
        _v, r = j.calculo()
        self.assertAlmostEqual(r["preco"], round(r["preco_base"] * 0.9, 2))
        j.silencioso = True
        pdf = j.gerar_pdf(os.path.join(d, "orc.pdf"))
        self.assertTrue(os.path.getsize(pdf) > 1000)
        with open(pdf, "rb") as f:
            self.assertTrue(f.read(5).startswith(b"%PDF"))
        self.assertIn("PREÇO DE VENDA", j.resultado.text())
        self.assertIn("LUCRO ESTIMADO", j.resultado.text())
        self.assertIn("ESTIMATIVAS", j.resultado.text())  # tempo do programa = estimativa
        self.assertIn("1 unidade", j.texto_cliente())
        self.assertNotIn("custo", j.texto_cliente().lower())  # cliente não vê o custo
        j.close()
        w.close()


if __name__ == "__main__":
    unittest.main()
