"""Importar PDF e AI (Illustrator salvo com compatibilidade PDF): os desenhos vetoriais da 1ª página.

Lê os operadores de desenho do PDF (pypdf, licença BSD): m l c v y h re, cm q Q e blocos reaproveitados
(Form XObjects, Do). Cada caminho pintado (contorno e/ou preenchimento) vira um objeto. Caminhos só de
recorte (W n) não entram. Texto e imagens dentro do PDF não são importados (converta o texto em curvas no
programa de origem; importe imagens como PNG/JPG). Unidades: pontos (1/72 pol.) -> mm.
"""
import os
from collections import Counter

from PySide6.QtGui import QPainterPath, QTransform

from .importar_svg import Resultado

MAX_BYTES = 50 * 1024 * 1024
MAX_OPS = 2_000_000
MAX_PROF = 12  # blocos dentro de blocos
PT_MM = 25.4 / 72
PINTAR = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
FECHAR_E_PINTAR = {b"s", b"b", b"b*"}


class PdfInvalido(Exception):
    pass


def _nums(ops, n):
    if len(ops) < n:
        raise ValueError("operandos faltando")
    return [float(x) for x in ops[:n]]


def load(caminho, pagina_n=0) -> Resultado:
    """Vetores de uma página do PDF (`pagina_n`: 0 = 1ª)."""
    if os.path.getsize(caminho) > MAX_BYTES:
        raise PdfInvalido("Arquivo grande demais.")
    with open(caminho, "rb") as f:
        if b"%PDF" not in f.read(1024):
            raise PdfInvalido("Não é um PDF. Arquivos .AI precisam ter sido salvos com \"Criar arquivo compatível "
                              "com PDF\" (opção do Illustrator).")
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
        from pypdf.generic import ContentStream
    except ImportError as e:  # dependência opcional na execução a partir do código-fonte
        raise PdfInvalido("Leitor de PDF não instalado (pip install pypdf).") from e
    try:
        leitor = PdfReader(caminho, strict=False)
        if leitor.is_encrypted and not leitor.decrypt(""):
            raise PdfInvalido("PDF protegido por senha.")
        if not leitor.pages:
            raise PdfInvalido("PDF sem páginas.")
        if not 0 <= pagina_n < len(leitor.pages):
            raise PdfInvalido(f"O PDF não tem a página {pagina_n + 1}.")
        pagina = leitor.pages[pagina_n]
    except PdfReadError as e:
        raise PdfInvalido(f"PDF ilegível: {e}") from e

    res = Resultado()
    if len(leitor.pages) > 1:
        res.avisos.append(f"O PDF tem {len(leitor.pages)} páginas; só a {pagina_n + 1}ª foi importada.")
    if int(pagina.get("/Rotate", 0) or 0) % 360:
        res.avisos.append("A página tem rotação definida no PDF; o desenho entra sem essa rotação.")
    caixa = pagina.mediabox
    x0, y1 = float(caixa.left), float(caixa.top)
    # PDF (pontos, Y para cima, origem em baixo) -> documento (mm, Y para baixo, origem no topo da página)
    pagina_mm = QTransform(PT_MM, 0, 0, -PT_MM, -x0 * PT_MM, y1 * PT_MM)
    ignorados, total = Counter(), [0]

    def executar(stream, recursos, ctm, prof):
        if prof > MAX_PROF:
            res.avisos.append("Blocos aninhados demais: parte do desenho foi ignorada.")
            return
        try:
            ops = ContentStream(stream, leitor).operations
        except Exception as e:  # conteúdo corrompido: importa o que deu
            res.avisos.append(f"Trecho do PDF ilegível ignorado ({type(e).__name__}).")
            return
        pilha, cam, atual = [], QPainterPath(), None
        for operandos, op in ops:
            total[0] += 1
            if total[0] > MAX_OPS:
                raise PdfInvalido("PDF complexo demais para importar.")
            try:
                if op == b"q":
                    pilha.append(ctm)
                elif op == b"Q":
                    ctm = pilha.pop() if pilha else ctm
                elif op == b"cm":
                    a, b, c, d, e, f = _nums(operandos, 6)
                    ctm = QTransform(a, b, c, d, e, f) * ctm
                elif op == b"m":
                    x, y = _nums(operandos, 2)
                    cam.moveTo(x, y)
                    atual = (x, y)
                elif op == b"l":
                    x, y = _nums(operandos, 2)
                    cam.lineTo(x, y)
                    atual = (x, y)
                elif op == b"c":
                    v = _nums(operandos, 6)
                    cam.cubicTo(*v)
                    atual = (v[4], v[5])
                elif op == b"v" and atual:  # 1º controle = ponto atual
                    v = _nums(operandos, 4)
                    cam.cubicTo(*atual, *v)
                    atual = (v[2], v[3])
                elif op == b"y":  # 2º controle = ponto final
                    v = _nums(operandos, 4)
                    cam.cubicTo(v[0], v[1], v[2], v[3], v[2], v[3])
                    atual = (v[2], v[3])
                elif op == b"h":
                    cam.closeSubpath()
                elif op == b"re":
                    x, y, w, h = _nums(operandos, 4)
                    cam.addRect(x, y, w, h)
                    atual = (x, y)
                elif op in PINTAR or op == b"n":
                    if op in FECHAR_E_PINTAR:
                        cam.closeSubpath()
                    if op != b"n" and not cam.isEmpty():
                        res.objetos.append((f"PDF caminho {len(res.objetos) + 1}", (ctm * pagina_mm).map(cam)))
                    cam, atual = QPainterPath(), None
                elif op == b"Do":
                    xo = recursos.get("/XObject", {}) if recursos else {}
                    obj = xo.get(operandos[0]) if xo else None
                    obj = obj.get_object() if obj is not None else None
                    if obj is None:
                        ignorados["bloco ausente"] += 1
                    elif obj.get("/Subtype") == "/Form":
                        m = [float(v) for v in obj.get("/Matrix", [1, 0, 0, 1, 0, 0])]
                        sub = obj.get("/Resources")
                        executar(obj, sub.get_object() if sub is not None else recursos, QTransform(*m) * ctm,
                                 prof + 1)
                    else:
                        ignorados["imagem dentro do PDF"] += 1
                elif op in (b"Tj", b"TJ", b"'", b'"'):  # só o que escreve texto (BT/ET vazios não contam)
                    ignorados["texto (converta em curvas antes)"] += 1
                elif op in (b"BI", b"sh"):
                    ignorados["imagem/degradê dentro do PDF"] += 1
            except (ValueError, TypeError, IndexError):
                ignorados[f"operador {op.decode(errors='replace')} malformado"] += 1

    recursos = pagina.get("/Resources")
    conteudo = pagina.get_contents()
    if conteudo is not None:
        executar(conteudo, recursos.get_object() if recursos is not None else {}, QTransform(), 0)
    res.ignorados.update(ignorados)
    return res
