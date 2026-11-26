"""Placa PIX Milli: QR lê o Pix exato, rasgos da placa e dos pés com a MESMA largura (encaixe justo, sem cola)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tools", "projetos"))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import placa_pix_milli as pm  # noqa: E402


def larguras_rasgos(path):
    """Larguras dos rasgos = trechos horizontais curtos (< 5 mm) do contorno."""
    q = path.toSubpathPolygons()[0]
    out = []
    for i in range(q.size() - 1):
        a, b = q[i], q[i + 1]
        if abs(a.y() - b.y()) < 1e-6 and 0.5 < abs(a.x() - b.x()) < 5:
            out.append(round(abs(a.x() - b.x()), 3))
    return out


class PlacaPixMilliTest(unittest.TestCase):
    def test_encaixes_iguais_e_medidas(self):
        lp, le = larguras_rasgos(pm.placa_contorno()), larguras_rasgos(pm.pe_contorno())
        self.assertEqual(lp, [pm.RASGO, pm.RASGO])  # 2 rasgos na placa
        self.assertEqual(le, [pm.RASGO])            # 1 rasgo no pé, mesma largura
        self.assertLess(pm.RASGO, 2.9)              # justo em MDF de ~2,9 mm (kerf abre ~0,1)
        self.assertEqual(pm.FUNDO * 2, pm.PE_H)     # encaixe em cruz fecha a altura do pé
        b = pm.placa_contorno().boundingRect()
        self.assertAlmostEqual(b.width(), 110, 3)
        self.assertAlmostEqual(b.height(), 160, 3)

    @unittest.skipUnless(os.path.exists(pm.PDF) and pm.PIX, "PDF ou Pix (privado/) da placa Milli não está neste PC")
    def test_gera_com_qr_valido(self):
        destino = os.path.join(tempfile.mkdtemp(), "milli.rbl")
        _d, qr, texto = pm.gerar(pm.PDF, destino)  # gerar() já lê o QR e compara com o Pix (assert)
        self.assertAlmostEqual(qr.boundingRect().width(), 51.75, 1)
        self.assertGreater(texto.elementCount(), 100)
        self.assertEqual(pm.crc16(pm.PIX[:-4]), "5F07")


if __name__ == "__main__":
    unittest.main()
