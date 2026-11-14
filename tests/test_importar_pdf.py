"""Importar PDF/AI: medidas exatas em mm, Y para baixo, blocos (Form XObjects), texto avisado, recorte ignorado."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import importar_pdf as ip  # noqa: E402

app = QApplication.instance() or QApplication([])

try:
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
except ImportError:  # reportlab só gera os PDFs de teste
    canvas = None


def caixa(path):
    r = path.boundingRect()
    return tuple(round(v, 3) for v in (r.left(), r.top(), r.width(), r.height()))


@unittest.skipIf(canvas is None, "reportlab não instalado")
class ImportarPdfTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def pdf(self, desenhar, paginas=1, nome="t.pdf"):
        p = os.path.join(self.tmp.name, nome)
        c = canvas.Canvas(p, pagesize=(200 * mm, 100 * mm))
        for _ in range(paginas):
            desenhar(c)
            c.showPage()
        c.save()
        return p

    def test_retangulo_bloco_texto_e_recorte(self):
        def d(c):
            c.rect(10 * mm, 10 * mm, 50 * mm, 20 * mm, stroke=1, fill=0)  # de baixo para cima no PDF
            c.beginForm("f1")
            c.circle(0, 0, 5 * mm, stroke=1, fill=1)
            c.endForm()
            c.saveState()
            c.translate(100 * mm, 50 * mm)
            c.doForm("f1")
            c.restoreState()
            c.saveState()
            p = c.beginPath()
            p.rect(0, 0, 30 * mm, 30 * mm)
            c.clipPath(p, stroke=0, fill=0)  # só recorte: não pode virar objeto
            c.restoreState()
            c.drawString(20 * mm, 80 * mm, "Ola")
        res = ip.load(self.pdf(d))
        caixas = sorted(caixa(p) for _, p in res.objetos)
        self.assertEqual(caixas, [(10.0, 70.0, 50.0, 20.0), (95.0, 45.0, 10.0, 10.0)])  # Y para baixo (100 - 30)
        self.assertEqual(res.ignorados["texto (converta em curvas antes)"], 1)
        self.assertEqual(res.avisos, [])

    def test_varias_paginas_avisa(self):
        res = ip.load(self.pdf(lambda c: c.line(0, 0, 10 * mm, 0), paginas=3))
        self.assertEqual(len(res.objetos), 1)
        self.assertTrue(any("3 páginas" in a for a in res.avisos))

    def test_ai_com_pdf_dentro_e_arquivo_errado(self):
        ai = self.pdf(lambda c: c.line(0, 0, 10 * mm, 0), nome="arte.ai")
        self.assertEqual(len(ip.load(ai).objetos), 1)
        ruim = os.path.join(self.tmp.name, "velho.ai")
        with open(ruim, "w") as f:
            f.write("%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator 8\n")
        with self.assertRaises(ip.PdfInvalido):
            ip.load(ruim)

    def test_pela_janela(self):
        from PySide6.QtCore import QSettings
        from redblack.ui.main_window import MainWindow
        p = self.pdf(lambda c: c.rect(10 * mm, 10 * mm, 40 * mm, 20 * mm))
        w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        msgs = []
        w.show_info = w.show_error = lambda t, m: msgs.append(m)  # sem janelas modais no teste
        antes = len(w.canvas.view.shapes())
        self.assertTrue(w.import_path(p))
        self.assertEqual(len(w.canvas.view.shapes()), antes + 1, msgs)
        w.close()


if __name__ == "__main__":
    unittest.main()
