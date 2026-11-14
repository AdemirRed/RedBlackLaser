"""Código QR próprio, conferido com o leitor do OpenCV."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import qrcode_rb as q  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
try:
    import cv2
    import numpy as np
except ImportError:  # leitor só para conferir; o programa não depende dele
    cv2 = None


def ler(m):
    n, esc, borda = len(m), 8, 4
    img = np.full(((n + 2 * borda) * esc,) * 2, 255, np.uint8)
    for y in range(n):
        for x in range(n):
            if m[y][x]:
                img[(y + borda) * esc:(y + borda + 1) * esc, (x + borda) * esc:(x + borda + 1) * esc] = 0
    return cv2.QRCodeDetector().detectAndDecode(img)[0]


class QrTest(unittest.TestCase):
    @unittest.skipIf(cv2 is None, "OpenCV não instalado")
    def test_leitura_independente(self):
        for t in ("RedBlack", "https://redblack.com.br/p/123", "Olá, João! ç", "N" * 60, "z" * 210):
            self.assertEqual(ler(q.matriz(t)), t)

    def test_tamanhos_e_limite(self):
        self.assertEqual(len(q.matriz("A")), 21)                            # versão 1
        self.assertEqual(len(q.matriz("z" * 210)), 57)                       # versão 10
        with self.assertRaises(q.TextoLongoDemais):
            q.matriz("z" * 300)
        p = q.caminho("RedBlack", 21)
        self.assertLessEqual(p.boundingRect().width(), 21)

    def test_na_janela(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        self.assertTrue(w.criar_qr({"texto": "RedBlack", "lado": 30.0, "camada": "C02"}))
        s = w.canvas.view.shapes()[0]
        self.assertEqual((s.name, s.layer), ("QR: RedBlack", "C02"))
        self.assertFalse(w.criar_qr({"texto": "   ", "lado": 30.0, "camada": "C02"}))
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()


class DialogoValoresTest(unittest.TestCase):
    def test_tipos_de_campo(self):
        from PySide6.QtWidgets import QComboBox, QLineEdit
        from redblack.ui.dialogo_valores import ValoresDialog
        d = ValoresDialog(None, "t", [("texto", "T", "abc", None), ("camada", "C", "C02", [("C01", "C01"), ("C02", "C02")]),
                                      ("n", "N", 3, (1, 9, 0, "")), ("ok", "OK", True, None)])
        self.assertIsInstance(d.w["texto"], QLineEdit)
        self.assertIsInstance(d.w["camada"], QComboBox)                       # lista, mesmo com padrão em texto
        self.assertEqual(d.valores(), {"texto": "abc", "camada": "C02", "n": 3, "ok": True})
