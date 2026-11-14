"""Código de barras EAN-13 próprio, conferido com o leitor do OpenCV."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import codigo_barras as cb  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
try:
    import cv2
    import numpy as np
    cv2.barcode.BarcodeDetector
except (ImportError, AttributeError):
    cv2 = None


def ler(bits):
    mod, quiet = 2, 10
    for alt in (100, 60):
        img = np.full((alt + 20, (len(bits) + 2 * quiet) * mod), 255, np.uint8)
        for i, b in enumerate(bits):
            if b == "1":
                img[10:10 + alt, (quiet + i) * mod:(quiet + i + 1) * mod] = 0
        r = cv2.barcode.BarcodeDetector().detectAndDecode(cv2.GaussianBlur(img, (3, 3), 0))[0]
        if r:
            return r
    return ""


class Ean13Test(unittest.TestCase):
    def test_digito_e_validacao(self):
        self.assertEqual(cb.barras("400638133393")[1], "4006381333931")
        self.assertEqual(len(cb.barras("400638133393")[0]), 95)
        for ruim in ("123", "4006381333932", "12345678901a"):
            with self.assertRaises(cb.NumeroInvalido):
                cb.barras(ruim)

    @unittest.skipIf(cv2 is None, "leitor de código de barras do OpenCV indisponível")
    def test_leitura_independente_todos_os_primeiros_digitos(self):
        for d in range(1, 10):
            bits, n = cb.barras(f"{d}23456789012"[:12])
            self.assertEqual(ler(bits), n)

    def test_na_janela(self):
        tmp = tempfile.TemporaryDirectory()
        w = MainWindow(QSettings(os.path.join(tmp.name, "t.ini"), QSettings.IniFormat))
        w.ask_save = lambda: "discard"
        w.new_document()
        self.assertTrue(w.criar_ean13({"numero": "789123456789", "largura": 31.35, "altura": 22.85,
                                       "legenda": True, "camada": "C03"}))
        nomes = sorted(s.name for s in w.canvas.view.shapes())
        self.assertEqual(nomes, ["EAN-13 7891234567895", "EAN-13 7891234567895 (números)"])
        w.show_error = lambda *a: None
        self.assertFalse(w.criar_ean13({"numero": "12", "largura": 31.35, "altura": 22.85, "legenda": False,
                                        "camada": "C03"}))
        w.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
