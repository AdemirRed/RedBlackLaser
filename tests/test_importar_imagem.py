"""Etapa 6: dimensões físicas e proporção corretas; imagem original preservada."""
import base64
import json
import os
import struct
import sys
import tempfile
import unittest
import zlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))  # offscreen não vê fontes do sistema
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QSettings  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import importar_imagem as im  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


# ---------- geradores de arquivos de teste ----------
def png_raw(w, h, phys=None, rgb=(255, 0, 0)):
    """PNG escrito à mão: controle total sobre o bloco pHYs (phys=(x, y, unidade) ou None)."""
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    if phys:
        out += chunk(b"pHYs", struct.pack(">IIB", *phys))
    return out + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def qt_bytes(w, h, fmt, dpi):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("#00aa00"))
    img.setDotsPerMeterX(round(dpi / 0.0254))
    img.setDotsPerMeterY(round(dpi / 0.0254))
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, fmt)
    return bytes(buf.data())


def jfif_patch(data, unit, x, y):
    assert data[6:11] == b"JFIF\x00"
    return data[:13] + struct.pack(">BHH", unit, x, y) + data[18:]


def with_exif_orientation(data, orientation):
    """Insere APP1 EXIF mínimo (só Orientation) logo após o APP0 JFIF."""
    tiff = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", 1) + \
        struct.pack("<HHIHH", 0x0112, 3, 1, orientation, 0) + struct.pack("<I", 0)
    payload = b"Exif\x00\x00" + tiff
    app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    app0_end = 4 + struct.unpack(">H", data[4:6])[0]
    return data[:app0_end] + app1 + data[app0_end:]


class LeituraTest(unittest.TestCase):
    def test_png_com_dpi_do_qt(self):
        data = qt_bytes(600, 300, "PNG", 300)
        r = im.from_bytes(data, "a.png")
        dpm = round(300 / 0.0254)  # valor inteiro gravado no pHYs
        self.assertTrue(r.dpi_do_arquivo)
        self.assertAlmostEqual(r.largura_mm, 600 / dpm * 1000, delta=1e-9)
        self.assertAlmostEqual(r.altura_mm, 300 / dpm * 1000, delta=1e-9)
        self.assertAlmostEqual(r.largura_mm, 50.8, delta=0.01)  # 2 pol

    def test_png_sem_phys_e_com_unidade_desconhecida(self):
        for phys in (None, (10, 10, 0)):  # unidade 0 = só proporção
            r = im.from_bytes(png_raw(96, 48, phys), "a.png")
            self.assertFalse(r.dpi_do_arquivo, phys)
            self.assertAlmostEqual(r.largura_mm, 25.4)
            self.assertAlmostEqual(r.altura_mm, 12.7)

    def test_png_dpi_diferente_por_eixo(self):
        r = im.from_bytes(png_raw(100, 100, (3937, 7874, 1)), "a.png")  # ~100 × ~200 dpi
        self.assertAlmostEqual(r.largura_mm, 100 / 3937 * 1000, delta=1e-9)
        self.assertAlmostEqual(r.altura_mm, 100 / 7874 * 1000, delta=1e-9)

    def test_jpeg_jfif_dpi_dpcm_e_sem_densidade(self):
        base = qt_bytes(254, 127, "JPEG", 200)
        self.assertAlmostEqual(im.from_bytes(jfif_patch(base, 1, 254, 254), "a.jpg").largura_mm, 25.4)
        r = im.from_bytes(jfif_patch(base, 2, 100, 100), "a.jpg")  # 100 pontos/cm = 254 dpi
        self.assertAlmostEqual(r.dpi[0], 254)
        self.assertAlmostEqual(r.largura_mm, 25.4)
        r = im.from_bytes(jfif_patch(base, 0, 1, 1), "a.jpg")
        self.assertFalse(r.dpi_do_arquivo)
        self.assertAlmostEqual(r.largura_mm, 254 / 96 * 25.4)

    def test_orientacao_exif_troca_eixos_e_dpi(self):
        base = jfif_patch(qt_bytes(40, 20, "JPEG", 100), 1, 100, 200)
        r = im.from_bytes(with_exif_orientation(base, 6), "foto.jpg")  # 6 = girar 90° horário
        self.assertEqual((r.imagem.qimage.width(), r.imagem.qimage.height()), (20, 40))
        self.assertAlmostEqual(r.largura_mm, 20 / 200 * 25.4)
        self.assertAlmostEqual(r.altura_mm, 40 / 100 * 25.4)

    def test_original_preservado_byte_a_byte(self):
        data = png_raw(10, 10, (11811, 11811, 1))
        r = im.from_bytes(data, "a.png")
        self.assertIs(r.imagem.dados, data)
        import hashlib
        self.assertEqual(r.imagem.sha256, hashlib.sha256(data).hexdigest())

    def test_invalidos(self):
        for data in (b"GIF89a....", b"", png_raw(5, 5)[:40], b"\xff\xd8\xff\xe0lixo"):
            with self.assertRaises(im.ImagemInvalida):
                im.from_bytes(data, "x")

    def test_extensao_errada_usa_conteudo(self):
        self.assertEqual(im.from_bytes(png_raw(4, 4), "na_verdade_png.jpg").imagem.formato, "png")


class ProjetoComImagemTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def snap(self):
        r = im.from_bytes(png_raw(30, 20, (11811, 11811, 1)), "logo.png")
        s = ob.ImageShape(r.imagem, r.largura_mm, r.altura_mm, "logo.png")
        ob.rotate([s], 17, QPointF(3, 4))
        return s.snapshot()

    def test_ida_e_volta(self):
        snap = self.snap()
        p = os.path.join(self.tmp.name, "p.rbl")
        pj.save(p, [snap])
        got = pj.load(p)[0]
        self.assertEqual(got[5].dados, snap[5].dados)          # bytes originais idênticos
        self.assertEqual(got[1], snap[1])                      # matriz exata
        self.assertEqual(pj.path_to_list(got[0]), pj.path_to_list(snap[0]))
        self.assertEqual(got[5].arquivo, "logo.png")
        restored = ob.from_snapshot(got)
        self.assertIsInstance(restored, ob.ImageShape)
        self.assertEqual(restored.imagem.qimage.size().toTuple(), (30, 20))

    def test_imagem_corrompida_e_rejeitada(self):
        d = pj.to_dict([self.snap()])
        raw = d["objetos"][0]["imagem"]
        cases = [{**raw, "sha256": "0" * 64}, {**raw, "dados": "@@@"},
                 {**raw, "formato": "jpeg"}, None]
        for bad in cases:
            obj = {**d["objetos"][0], "imagem": bad}
            with self.assertRaises(pj.ProjetoInvalido, msg=str(bad)[:40]):
                pj.from_dict({**d, "objetos": [obj]})

    def test_projeto_versao_1_continua_legivel(self):
        v1 = {"formato": "redblack-laser", "versao": 1, "unidade": "mm", "objetos": [
            {"nome": "r", "camada": "C01", "cor": "#4aa3ff", "matriz": [1, 0, 0, 0, 1, 0, 0, 0, 1],
             "preenchimento": "oddeven", "caminho": [["M", 0, 0], ["L", 10, 0], ["L", 10, 5]]}]}
        snaps = pj.from_dict(json.loads(json.dumps(v1)))
        self.assertIsNone(snaps[0][5])


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(("erro", m))
        self.win.show_info = lambda t, m: self.msgs.append(("info", m))
        self.win.resize(1400, 900)
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def write(self, data, name):
        p = os.path.join(self.tmp.name, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def test_importar_medidas_proporcao_desfazer(self):
        p = self.write(png_raw(200, 100, (11811, 11811, 1)), "placa.png")  # 300 dpi
        self.assertTrue(self.win.import_path(p))
        self.assertEqual(self.msgs, [])  # DPI presente: sem aviso
        f = self.win.fields
        self.assertAlmostEqual(f["w"].value(), 200 / 11811 * 1000, places=2)
        self.assertAlmostEqual(f["h"].value(), 100 / 11811 * 1000, places=2)
        self.assertTrue(self.win.lock.isChecked())
        f["w"].setValue(80)
        f["w"].editingFinished.emit()
        r = ob.geom_rect(self.view.selected()[0])
        self.assertAlmostEqual(r.width() / r.height(), 2, delta=1e-9)  # proporção mantida
        self.assertAlmostEqual(r.width(), 80, delta=1e-9)
        self.win.undo_stack.undo()
        self.win.undo_stack.undo()
        self.assertFalse(any(isinstance(s, ob.ImageShape) for s in self.view.shapes()))

    def test_sem_dpi_avisa(self):
        self.assertTrue(self.win.import_path(self.write(png_raw(96, 96), "sem_dpi.png")))
        self.assertEqual(self.msgs[0][0], "info")
        self.assertIn("96 dpi", self.msgs[0][1])
        self.assertIn("sem_dpi.png: 96×96 px a 96 dpi = 25,40 × 25,40 mm", self.msgs[0][1])
        self.assertAlmostEqual(self.win.fields["w"].value(), 25.4)

    def test_arquivo_invalido_nao_altera(self):
        n = len(self.view.shapes())
        self.assertFalse(self.win.import_path(self.write(b"GIF89a", "x.png")))
        self.assertEqual(len(self.view.shapes()), n)
        self.assertEqual(self.win.undo_stack.count(), 0)

    def test_imagem_e_desenhada_no_lugar_certo(self):
        self.win.new_document()
        self.win.import_path(self.write(png_raw(100, 100, (3937, 3937, 1), rgb=(255, 0, 0)), "verm.png"))
        img = ob.ImageShape  # noqa: F841
        s = self.view.selected()[0]
        self.win.canvas.scene.clearSelection()  # sem caixa de seleção por cima
        app.processEvents()
        c = self.view.mapFromScene(ob.geom_rect(s).center())
        frame = self.view.viewport().grab().toImage()
        px = frame.pixelColor(c)
        self.assertGreater(px.red(), 200)
        self.assertLess(px.green(), 60)

    def test_copiar_colar_salvar_reabrir_preserva_original(self):
        data = with_exif_orientation(jfif_patch(qt_bytes(40, 20, "JPEG", 100), 1, 150, 150), 6)
        self.assertTrue(self.win.import_path(self.write(data, "foto.jpg")))
        self.win.copy()
        self.win.paste()
        p = os.path.join(self.tmp.name, "proj.rbl")
        self.assertTrue(self.win.save_to(p))
        with open(p, encoding="utf-8") as fh:
            saved = [o for o in json.load(fh)["objetos"] if o["tipo"] == "imagem"]
        self.assertEqual(len(saved), 2)
        self.assertTrue(all(base64.b64decode(o["imagem"]["dados"]) == data for o in saved))
        self.win.new_document()
        self.assertTrue(self.win.open_path(p))
        imgs = [s for s in self.view.shapes() if isinstance(s, ob.ImageShape)]
        self.assertEqual(len(imgs), 2)
        self.assertEqual(imgs[0].imagem.dados, data)
        r = ob.geom_rect(imgs[0])
        self.assertAlmostEqual(r.width(), 20 / 150 * 25.4, delta=1e-9)   # orientação EXIF mantida
        self.assertAlmostEqual(r.height(), 40 / 150 * 25.4, delta=1e-9)


if __name__ == "__main__":
    unittest.main()
