"""Porta-retrato Isabella e Nathan: classificação por profundidade (peça dentro de vazado corta antes) e, se o PDF
estiver disponível, o projeto completo abre e gera G-code em todas as abas, na ordem das camadas."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tools", "projetos"))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import porta_retrato_isabella_nathan as pr  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import geometria as g  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
PDF = os.environ.get("PDF_PORTA_RETRATO", r"F:\Downloads\porta_retrato_isabella_nathan_coracoes_projeto (1).pdf")


class PortaRetratoTest(unittest.TestCase):
    def test_coracao_na_janela_corta_antes(self):
        contorno = fm.rect_path(QRectF(0, 0, 100, 100))
        janela = fm.rect_path(QRectF(10, 10, 80, 80))
        coracao = fm.ellipse_path(QRectF(20, 20, 10, 10))
        furo = fm.ellipse_path(QRectF(23, 23, 2, 2))  # furo dentro do coração
        outro = fm.rect_path(QRectF(200, 0, 20, 20))  # outra peça solta
        res = pr.classificar([contorno, janela, coracao, furo, outro], 3)
        self.assertEqual([lid for _, lid, _ in res], ["C01", "C02", "C03", "C07", "C01"])
        self.assertEqual([d for *_, d in res], [0, 0, 2, 2, 4])  # janela é do contorno; furo é do coração
        for c in pr.camadas():  # corte 650 mm/min, nunca acima de 85 %
            self.assertEqual((c.velocidade_mm_min, c.potencia_max, c.passadas), (650, 85, 2))

    def test_camada_de_cima_da_base_sem_folga(self):
        partes = [pr.parte_base(a, b) for a, b in zip(pr.CORTES_BASE, pr.CORTES_BASE[1:])]
        self.assertEqual(sum(p[0].boundingRect().width() for p in partes), 426)
        rasgos = sorted(round(a + r.boundingRect().x(), 3) for a, p in zip(pr.CORTES_BASE, partes) for r in p[1:])
        self.assertEqual(rasgos, list(pr.RASGOS_BASE))
        for p in partes:
            for r in p[1:]:
                self.assertEqual((r.boundingRect().y(), r.boundingRect().width(), r.boundingRect().height()), (13, 26, 9))  # 3 + 3 + 3
        self.assertTrue(all(abs(c - 142) > 20 for c in pr.CORTES_BASE[1:-1]))  # emendas desencontradas

    @unittest.skipUnless(os.path.exists(PDF), "PDF do porta-retrato não disponível")
    def test_sobras_das_janelas(self):
        subs = pr.otimizar(pr.ler_pdf(PDF))
        for n, esp in ((5, 3), (6, 3)):
            itens = pr.classificar(subs[n], esp)
            janela = next(s for s, lid, _ in itens if lid == "C02" and s.boundingRect().width() > 140)
            jr = janela.boundingRect().adjusted(2, 2, -2, -2)
            pecas = [s for s, lid, _ in itens if lid == "C03"]
            for i, a in enumerate(pecas):
                self.assertTrue(jr.contains(a.boundingRect()), (n, a.boundingRect()))  # 2 mm de folga da janela
                for b in pecas[i + 1:]:  # área real (o par de triângulos divide a mesma caixa, como no PDF)
                    self.assertFalse(a.intersects(b), (n, a.boundingRect(), b.boundingRect()))
        coracoes = sum(1 for n in (5, 6) for s, lid, _ in pr.classificar(subs[n], 3)
                       if lid == "C03" and s.elementCount() > 50)
        self.assertEqual(coracoes, 18)
        # aba 9: base lisa 142, camada do meio 205 + 221 (2 rasgos 26 × 9 cada) e um par de triângulos
        caixas9 = sorted((round(s.boundingRect().width(), 2), round(s.boundingRect().height(), 2)) for s in subs[9])
        self.assertEqual(caixas9, [(26, 9)] * 4 + [(36, 36)] * 2 + [(142, 62), (205, 62), (221, 62)])
        triangulos = [s for n in (6, 9) for s in subs[n] if round(s.boundingRect().width()) == 36]
        self.assertEqual(len(triangulos), 4)  # 2 apoios = 4 triângulos de 3 mm colados aos pares
        r8 = [s.boundingRect() for s in subs[8] if pr.profundidades([s] + subs[8])[0] == 0]
        for i, a in enumerate(r8):
            self.assertTrue(QRectF(0, 0, 365, 370).contains(a))
            for b in r8[i + 1:]:
                self.assertFalse(a.adjusted(-1, -1, 1, 1).intersects(b), (a, b))

    @unittest.skipUnless(os.path.exists(PDF), "PDF do porta-retrato não disponível")
    def test_projeto_completo(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = pr.gerar(PDF, os.path.join(tmp, "pr.rbl"))
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            w.show_info = w.show_error = lambda *a: None
            try:
                g.definir_mesa(365, 370)
                self.assertTrue(w.open_path(arq))
                self.assertEqual(len(w.paginas), 5)
                for i in range(5):
                    w.ir_para_pagina(i)
                    destino = os.path.join(tmp, f"f{i}.gcode")
                    self.assertTrue(w.export_gcode_to(destino), w.nomes_paginas[i])
                    with open(destino, encoding="utf-8") as f:
                        txt = f.read()
                    info = gc.analisar(txt)
                    self.assertTrue(info["dentro_da_area"] and info["fim_desligado"], w.nomes_paginas[i])
                    ordem = [txt.find(f"; Camada {c}") for c in ("C07", "C03", "C02", "C01")]
                    presentes = [p for p in ordem if p >= 0]
                    self.assertEqual(presentes, sorted(presentes), w.nomes_paginas[i])
            finally:
                g.definir_mesa(400, 400)
                w.close()


if __name__ == "__main__":
    unittest.main()
