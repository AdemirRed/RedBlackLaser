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
        self.assertAlmostEqual(r["remun_maquina"], 4.37)   # 35 min × R$ 7,49/h
        self.assertAlmostEqual(r["manual"], 0.50)         # 10 min × R$ 3/h
        self.assertAlmostEqual(r["desembolso"], 6.42)     # dinheiro que sai de fato
        self.assertAlmostEqual(r["custo"], 6.42)          # laser e mão de obra são ganho do dono, não custo
        self.assertAlmostEqual(r["preco"], 36.87)          # 3 × R$ 6 + pintura R$ 14 + laser + mão de obra
        self.assertAlmostEqual(r["lucro"], 30.45)
        carine = orc.orcar({"camadas": 3, "laser_min": 176.2, "manual_min": 120})  # calibrado com o dono
        self.assertAlmostEqual(carine["preco"], 60.0)
        self.assertTrue(35 <= orc.orcar(dict(orc.MODELOS_INICIAIS["Valentina Hellena"]))["preco"] <= 40)
        longo = orc.orcar({"camadas": 3, "laser_min": 180})  # 3 h de laser cobrando por placa: nunca "prejuízo"
        self.assertGreater(longo["lucro"], 0)
        t = orc.tabela_descontos(dict(orc.MODELOS_INICIAIS["Valentina Hellena"]))
        self.assertEqual([x[0] for x in t], [1, 5, 10, 20])
        self.assertAlmostEqual(t[3][2], 30.39)             # 15 % de desconto em 20+ (R$ 35,75 − 15 %)
        self.assertTrue(orc.dicas(r, orc.MODELOS_INICIAIS["Tyfani"] | {k: d for k, (_, d, _t) in orc.CAMPOS.items()
                                                                          if k not in orc.MODELOS_INICIAIS["Tyfani"]}))
        with self.assertRaises(ValueError):
            orc.orcar({"camadas": 0})

    def test_preco_por_placa_e_pintura(self):
        r = orc.orcar({"camadas": 3})  # padrão: R$ 6 por placa + pintura R$ 14 (até 10 placas)
        self.assertTrue(r["por_placa"])
        self.assertAlmostEqual(r["cobr_placas"], 18.0)
        self.assertAlmostEqual(r["cobr_pintura"], 14.0)
        self.assertAlmostEqual(r["preco"], 32.0)
        r = orc.orcar({"camadas": 12})  # 2 placas acima de 10: + 2 × R$ 3 na pintura
        self.assertAlmostEqual(r["cobr_pintura"], 20.0)
        self.assertAlmostEqual(r["preco"], 12 * 6 + 20)
        r = orc.orcar({"camadas": 12, "pintura": 0})  # sem pintura: só as placas, e a tinta sai do custo
        self.assertAlmostEqual(r["preco"], 72.0)
        self.assertEqual(r["tinta"], 0.0)
        self.assertAlmostEqual(orc.orcar({"camadas": 3, "preco_manual": 70})["preco"], 70.0)  # preço na mão vence
        r = orc.orcar({"camadas": 3, "laser_min": 60, "manual_min": 30})  # corte e mão de obra: o cliente paga
        self.assertAlmostEqual(r["preco"], 18 + 14 + 7.49 + 1.5)
        self.assertAlmostEqual(r["custo"], r["desembolso"])  # mas não são custo

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
        self.assertAlmostEqual(j.valor_hora.value(), 7.49)  # calibrado: quadro da Carine = R$ 60
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
        j.campos["preco_manual"].setValue(0)
        j.campos["camadas"].setValue(3)
        j.campos["pintura"].setValue(1)
        self.assertIn("3 placa(s) de MDF × R$ 6,00", j.texto_cliente())
        self.assertIn("Placas cobradas", [j.tabela.item(i, 0).text() for i in range(j.tabela.rowCount())])
        j.close()
        w.close()


if __name__ == "__main__":
    unittest.main()
