"""Importação de PNG/JPG (Etapa 6).

Tamanho físico = pixels / DPI gravado no arquivo (PNG pHYs, JPEG JFIF ou EXIF via Qt).
Sem DPI no arquivo, assume DEFAULT_DPI e avisa. Os bytes originais são preservados sem
recompressão; a imagem exibida é decodificada deles (com orientação EXIF aplicada).
"""
import hashlib
import os
import struct
from dataclasses import dataclass, field

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QImageReader

DEFAULT_DPI = 96.0  # mesmo padrão do SVG; a referência também cai em ~96 quando falta DPI (fórum)
MAX_BYTES = 100 * 1024 * 1024
MAX_PIXELS = 100_000_000  # ~100 MP: protege a memória
FORMATS = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpeg"}


class ImagemInvalida(Exception):
    """Arquivo não pode ser importado; mensagem exibida ao usuário."""


@dataclass(eq=False, frozen=True)
class ImagemOriginal:
    dados: bytes                       # arquivo original, byte a byte
    formato: str                       # "png" | "jpeg"
    arquivo: str                       # nome do arquivo de origem (informativo)
    sha256: str
    qimage: QImage = field(repr=False)  # decodificada para exibição

    def __eq__(self, other):  # comparar pelo hash evita comparar megabytes a cada edição
        return isinstance(other, ImagemOriginal) and self.sha256 == other.sha256

    def __hash__(self):
        return hash(self.sha256)


@dataclass
class Importada:
    imagem: ImagemOriginal
    largura_mm: float
    altura_mm: float
    dpi: tuple            # (x, y) efetivos
    dpi_do_arquivo: bool  # False = DEFAULT_DPI assumido


def detect_format(data: bytes):
    return next((f for magic, f in FORMATS.items() if data.startswith(magic)), None)


def _png_dpi(data: bytes):
    pos = 8
    while pos + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        if ctype == b"pHYs" and length == 9:
            x, y, unit = struct.unpack(">IIB", data[pos + 8:pos + 17])
            if unit == 1 and x > 0 and y > 0:  # pixels por metro
                return x * 0.0254, y * 0.0254
            return None
        if ctype in (b"IDAT", b"IEND"):  # pHYs precisa vir antes de IDAT
            return None
        pos += 12 + length
    return None


def _jfif_dpi(data: bytes):
    if data[2:4] == b"\xff\xe0" and data[6:11] == b"JFIF\x00":
        unit, x, y = struct.unpack(">BHH", data[13:18])
        if x > 0 and y > 0:
            if unit == 1:
                return float(x), float(y)
            if unit == 2:  # pontos por cm
                return x * 2.54, y * 2.54
    return None


def file_dpi(data: bytes, fmt: str, img: QImage):
    """DPI gravado no arquivo, ou None. JPEG: JFIF primeiro; EXIF lido pelo Qt quando houver."""
    if fmt == "png":
        return _png_dpi(data)
    dpi = _jfif_dpi(data)
    if dpi is None and b"Exif\x00\x00" in data[:65536]:
        # O Qt aplica XResolution/YResolution do EXIF em dotsPerMeter.
        x, y = img.dotsPerMeterX() * 0.0254, img.dotsPerMeterY() * 0.0254
        if x > 1 and y > 1:
            dpi = (x, y)
    return dpi


def _buffer(data: bytes) -> QBuffer:
    buf = QBuffer()
    buf.setData(QByteArray(data))
    buf.open(QIODevice.ReadOnly)
    return buf


def decode(data: bytes) -> QImage:
    buf = _buffer(data)
    reader = QImageReader(buf)
    reader.setAutoTransform(True)  # orientação EXIF (fotos de celular)
    size = reader.size()
    if size.isValid() and size.width() * size.height() > MAX_PIXELS:
        raise ImagemInvalida(f"Imagem grande demais ({size.width()}×{size.height()} px; limite ~100 MP).")
    img = reader.read()
    if img.isNull():
        raise ImagemInvalida(f"Não foi possível decodificar a imagem: {reader.errorString()}")
    return img


def from_bytes(data: bytes, arquivo: str) -> Importada:
    fmt = detect_format(data)
    if fmt is None:
        raise ImagemInvalida("Formato não suportado: apenas PNG e JPEG.")
    img = decode(data)
    dpi = file_dpi(data, fmt, img)
    from_file = dpi is not None
    dx, dy = dpi if from_file else (DEFAULT_DPI, DEFAULT_DPI)
    # Orientação EXIF de 90°/270° troca os eixos da imagem; o DPI acompanha.
    buf = _buffer(data)
    raw = QImageReader(buf).size()
    if raw.isValid() and (raw.width(), raw.height()) == (img.height(), img.width()) and raw.width() != raw.height():
        dx, dy = dy, dx
    orig = ImagemOriginal(data, fmt, arquivo, hashlib.sha256(data).hexdigest(), img)
    return Importada(orig, img.width() / dx * 25.4, img.height() / dy * 25.4, (dx, dy), from_file)


def load(path: str) -> Importada:
    try:
        if os.path.getsize(path) > MAX_BYTES:
            raise ImagemInvalida("Arquivo de imagem grande demais (limite 100 MB).")
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise ImagemInvalida(f"Não foi possível ler o arquivo: {e}") from e
    return from_bytes(data, os.path.basename(path))
