"""Manual de montagem do presépio (PDF A4), desenhado com as próprias peças do PDF original.

As peças saem SEM código gravado: o manual mostra cada uma desenhada para reconhecer pelo formato.
Executar:  python tools/projetos/presepio_manual.py <Presepio_MDF_3mm_Projeto_Completo.pdf> <saida.pdf>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QMarginsF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter, QTransform  # noqa: E402

import presepio as pr  # noqa: E402
from carroca_manual import AZUL, CINZA, M, MADEIRA, TINTA, VERDE, VERM, W, Pagina, nota, seta  # noqa: E402

LARG = W - 2 * M
TOTAL = 7
# Mapa da base (página 6 do PDF): origem no canto inferior esquerdo, frente embaixo. Centro dos rasgos.
FIGURAS = {"P01": (120, 121), "P02": (170, 93), "P03": (205, 133), "P04": (99, 35), "P05": (244, 51),
           "P06": (307, 37), "P07": (39, 52), "P08": (28, 165)}
PAREDES = {"F01": ("x", 75.0), "F02": ("x", 215.0), "L01": ("y", 72.5), "L02": ("y", 307.5)}  # eixo, posição
BASE_W, BASE_H = 350.0, 230.0


def _parte(pc, k, tipos):
    out = QPainterPath()
    for p, t in pc[k]["partes"]:
        if t in tipos:
            out.addPath(p)
    return out


def peca(pg, pc, k, x, y, larg, alt, rotulo=True, fundo=MADEIRA, destaque=False):
    """Desenha a peça k (como no PDF: em pé, frente para o leitor) dentro da caixa (x, y, larg, alt)."""
    c = pc[k]["cont"].boundingRect()
    esc = min(larg / c.width(), alt / c.height())
    tf = QTransform.fromTranslate(-c.left(), -c.top()) * QTransform.fromScale(esc, esc) * QTransform.fromTranslate(
        x + (larg - c.width() * esc) / 2, y + (alt - c.height() * esc) / 2)
    pg.forma(pc[k]["cont"], tf, cor=VERM if destaque else TINTA, fundo=fundo, larg=0.5 if destaque else 0.3)
    pg.forma(_parte(pc, k, {"furo"}), tf, fundo="#ffffff", larg=0.2)
    grav = _parte(pc, k, {"cheio", "num"})
    if not grav.isEmpty():
        pg.p.setPen(Qt.NoPen)
        pg.forma(grav, tf, cor="#6b5a40", fundo="#6b5a40", larg=0.01)
    pg.forma(_parte(pc, k, {"linha"}), tf, cor="#8b7355", larg=0.12)
    if rotulo:
        pg.texto(x, y + alt + 0.8, larg, pr.NOMES[k], 7, True, AZUL, Qt.AlignHCenter)
    return tf


def cabecalho(pg, n, titulo, sub=""):
    pg.p.fillRect(QRectF(0, 0, W * pg.k, 22 * pg.k), Qt.black)
    pg.texto(M, 5, LARG, "PRESÉPIO · MDF 3 mm · manual de montagem", 8, True, "#e0a0a0")
    pg.texto(M, 10.5, LARG, titulo, 15, True, "#ffffff")
    pg.texto(M, H_PAG - 9, LARG, f"página {n} de {TOTAL}", 7, False, CINZA, Qt.AlignRight)
    if sub:
        return 26 + pg.texto(M, 26, LARG, sub, 9, False, CINZA) + 3
    return 28


H_PAG = 297.0


def passo(pg, y, n, titulo, itens, w=LARG, x=M):
    pg.p.setPen(Qt.NoPen)
    pg.forma(_circulo(x + 4, y + 4, 4), QTransform(), cor=VERM, fundo=VERM)
    pg.texto(x, y + 1.2, 8, str(n), 10, True, "#ffffff", Qt.AlignHCenter)
    y += pg.texto(x + 11, y + 0.8, w - 11, titulo, 11, True) + 2
    for it in itens:
        cor = VERM if it.startswith("ATENÇÃO") else TINTA
        y += pg.texto(x + 11, y, w - 11, "• " + it, 9, it.startswith("ATENÇÃO"), cor) + 1.2
    return y + 2


def _circulo(cx, cy, r):
    p = QPainterPath()
    p.addEllipse(cx - r, cy - r, 2 * r, 2 * r)
    return p


def caixa(pg, y, titulo, txt, cor=VERDE):
    alt = pg.texto(M + 4, y + 9, LARG - 8, txt, 8.5) + 13
    pg.p.setPen(Qt.NoPen)
    pg.forma(_ret(M, y, LARG, alt), QTransform(), cor=cor, fundo="#f2f7f2" if cor == VERDE else "#fdf0f0", larg=0.4)
    pg.texto(M + 4, y + 3, LARG - 8, titulo, 10, True, cor)
    pg.texto(M + 4, y + 9, LARG - 8, txt, 8.5)
    return y + alt + 4


def _ret(x, y, w, h):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return p


# ---------------------------------------------------------------- planta da base (vista de cima)
def planta(pg, pc, x, y, larg, mostrar=("paredes", "figuras"), destaque=(), legendas=True):
    """Base vista de cima, frente embaixo. Devolve a função (u, v) do mapa -> (x, y) na página."""
    esc = larg / BASE_W

    def em(u, v):
        return x + u * esc, y + (BASE_H - v) * esc

    pg.forma(_ret(x, y, BASE_W * esc, BASE_H * esc), QTransform(), fundo=MADEIRA, larg=0.4)
    b = pc["B01"]["cont"].boundingRect()
    tf = QTransform.fromTranslate(-b.left(), -b.top()) * QTransform.fromScale(esc, esc) * QTransform.fromTranslate(x, y)
    pg.forma(_parte(pc, "B01", {"furo"}), tf, cor=CINZA, fundo="#ffffff", larg=0.2)
    if "paredes" in mostrar:
        for k, (eixo, pos) in PAREDES.items():
            dest = k in destaque
            if eixo == "x":  # fachada/fundo: linha de 250 mm ao longo de x, centrada na casa
                x0, y0 = em(190 - 125, pos + 1.5)
                r = QRectF(x0, y0, 250 * esc, 3 * esc)
            else:
                x0, y0 = em(pos - 1.5, 225)
                r = QRectF(x0, y0, 3 * esc, 160 * esc)
            pg.forma(_ret(r.x(), r.y(), r.width(), r.height()), QTransform(), cor=VERM if dest else TINTA,
                     fundo=VERM if dest else "#7a6a52", larg=0.3)
            if legendas:
                if eixo == "x":
                    pg.texto(r.x(), r.y() + (4 if pos < 100 else -5), r.width(), pr.NOMES[k], 7, True,
                             VERM if dest else TINTA, Qt.AlignHCenter)
                else:
                    pg.texto(r.x() + (3 if pos < 100 else -32), r.center().y() - 2, 30, pr.NOMES[k], 7, True,
                             VERM if dest else TINTA, Qt.AlignLeft if pos < 100 else Qt.AlignRight)
    if "figuras" in mostrar:
        for k, (u, v) in FIGURAS.items():
            px, py = em(u, v)
            dest = k in destaque or not destaque
            pg.forma(_ret(px - 8 * esc, py - 1.5 * esc, 16 * esc, 3 * esc), QTransform(),
                     cor=VERM if dest else TINTA, fundo=VERM if dest else "#7a6a52", larg=0.2)
            if legendas:
                pg.texto(px - 15, py + 1.2, 30, pr.NOMES[k], 6.5, True, AZUL if dest else CINZA, Qt.AlignHCenter)
    fx, fy = em(BASE_W / 2, -2)
    pg.texto(fx - 30, fy + 1, 60, "▼ FRENTE (quem olha o presépio)", 7.5, True, VERM, Qt.AlignHCenter)
    return em


# ---------------------------------------------------------------- páginas
def pagina_capa(pg, pc):
    y = cabecalho(pg, 1, "Presépio com casa de encaixe",
                  "17 peças de MDF 3 mm, montadas só por encaixe (sem parafuso). Leia tudo uma vez antes de começar.")
    planta(pg, pc, M + 8, y + 2, LARG - 16)
    y += 2 + (LARG - 16) * BASE_H / BASE_W + 10
    y = caixa(pg, y, "Você vai precisar", "• As peças cortadas (3 chapas) e o gabarito de teste G01 + lingueta G02.\n"
              "• Lixa fina (220) para tirar a fumaça e ajustar encaixe apertado.\n"
              "• Opcional: cola branca (PVA) e um palito, só se quiser deixar o presépio fixo depois.")
    caixa(pg, y, "Regras de ouro", "1. Monte tudo A SECO primeiro. Cola, só no fim e se quiser.\n"
          "2. Nunca force um encaixe: se não entra com pressão leve, lixe a lingueta (não o rasgo).\n"
          "3. A frente gravada das figuras fica virada para a frente da base.\n"
          "4. As peças NÃO têm código gravado: reconheça pelo desenho da página 2.", VERM)


def pagina_pecas(pg, pc):
    y = cabecalho(pg, 2, "Conheça as peças", "Desenhadas em pé, como ficam montadas. Separe em 3 montes: casa, "
                  "telhado e figuras.")
    pg.texto(M, y, LARG, "CASA", 10, True, VERM)
    y += 6
    larg = (LARG - 12) / 3
    for i, k in enumerate(("B01", "F01", "F02")):
        peca(pg, pc, k, M + i * (larg + 6), y, larg, 36)
    y += 45
    for i, k in enumerate(("L01", "L02", "T01", "T02")):
        peca(pg, pc, k, M + i * (LARG / 4), y, LARG / 4 - 6, 32)
    y += 42
    y += pg.texto(M, y, LARG, "Laterais: L01 vai à ESQUERDA e L02 à DIREITA (olhando de frente). As duas são iguais: "
                  "qualquer uma serve em qualquer lado. Telhados também são iguais.", 8, False, CINZA) + 4
    pg.texto(M, y, LARG, "FIGURAS (a frente é o lado gravado)", 10, True, VERM)
    y += 6
    larg = LARG / 4
    for i, k in enumerate(("P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08")):
        peca(pg, pc, k, M + (i % 4) * larg, y + (i // 4) * 50, larg - 6, 40)
    y += 102
    pg.texto(M, y, LARG, "TESTE", 10, True, VERM)
    y += 6
    peca(pg, pc, "G01", M, y, 90, 16)
    peca(pg, pc, "G02", M + 100, y, 20, 16)
    pg.texto(M + 125, y + 2, LARG - 125, "G01 + G02: gabarito de folgas (página 3). Não fazem parte do presépio.",
             8, False, CINZA)


def pagina_teste(pg, pc):
    y = cabecalho(pg, 3, "Passo 0 — teste do encaixe", "Antes de montar, descubra se o seu MDF entra justo nos "
                  "rasgos de 3,00 mm.")
    peca(pg, pc, "G01", M + 10, y + 4, LARG - 60, 40, rotulo=False)
    peca(pg, pc, "G02", M + LARG - 40, y + 4, 30, 40, rotulo=False)
    seta(pg, M + LARG - 42, y + 24, M + LARG - 62, y + 24)
    y += 52
    y = passo(pg, y, 0, "Enfie a lingueta G02 em cada rasgo do G01", [
        "Os números gravados embaixo de cada rasgo são a largura dele: 2,80 até 3,20 mm.",
        "Procure o rasgo onde G02 entra com pressão leve e não balança.",
        "Se o justo for o 3,00: perfeito, tudo vai encaixar como no projeto.",
        "Se for 2,90 ou menor: o seu MDF está fino; uma gota de cola em cada encaixe resolve.",
        "Se só entrar no 3,10 ou maior: o seu MDF está grosso; lixe levemente as linguetas antes de montar.",
        "ATENÇÃO: lixe sempre a LINGUETA (a parte que entra), nunca o rasgo."])
    caixa(pg, y, "Dica", "Corte primeiro só a chapa 1 (base e laterais, onde estão G01 e G02) e faça o teste: se o "
          "encaixe estiver errado, você corrige antes de cortar as outras duas chapas.")


def pagina_casa(pg, pc):
    y = cabecalho(pg, 4, "Passos 1 e 2 — paredes na base", "As paredes se cruzam em 4 encaixes no meio da altura.")
    y = passo(pg, y, 1, "Laterais na base", [
        "Pegue L01 e L02 (as paredes com o X e as janelas da cerca).",
        "Os entalhes abertos (60 mm) ficam virados PARA CIMA.",
        "Encaixe as 2 linguetas de baixo de cada lateral nos rasgos compridos da base, uma de cada lado (vermelho "
        "no mapa).",
        "Lado gravado (a cerca) virado para fora."])
    peca(pg, pc, "L01", M, y + 4, 62, 48, rotulo=False, destaque=True)
    nota(pg, M, y + 55, "↑ entalhes para CIMA\n↓ linguetas na base", w=62, alinhar=Qt.AlignHCenter)
    planta(pg, pc, M + 72, y, LARG - 72, mostrar=("paredes",), destaque=("L01", "L02"))
    y += (LARG - 72) * BASE_H / BASE_W + 10
    y = passo(pg, y, 2, "Fachada e fundo descem cruzando as laterais", [
        "A fachada F01 (estrela e vão grande) vai na FRENTE; o fundo F02 (cerca) vai atrás.",
        "Os entalhes destas duas ficam virados PARA BAIXO: desça cada uma de cima, encaixando nos entalhes das "
        "laterais.",
        "No fim, as 2 linguetas de baixo entram nos rasgos curtos da base.",
        "ATENÇÃO: segure pela parte inteira, perto do encaixe; não aperte pelo meio do vão (o MDF pode quebrar)."])
    for i, k in enumerate(("F01", "F02")):
        peca(pg, pc, k, M + i * (LARG / 2), y + 2, LARG / 2 - 8, 46, destaque=True)
    nota(pg, M, y + 55, "↓ entalhes para BAIXO (os cortes perto das pontas, de baixo para cima)", w=LARG,
         alinhar=Qt.AlignHCenter)
    caixa(pg, y + 63, "Confira", "As 4 paredes apoiadas por inteiro na base, sem fresta embaixo, e os 4 cruzamentos "
          "encaixados até o fim (eles se encontram a 60 mm de altura).")


def pagina_figuras(pg, pc):
    y = cabecalho(pg, 5, "Passo 3 — figuras", "Cada figura tem uma lingueta no pé. O mapa mostra o rasgo de cada uma.")
    planta(pg, pc, M, y + 2, LARG, destaque=tuple(FIGURAS))
    y += 2 + LARG * BASE_H / BASE_W + 12
    y = passo(pg, y, 3, "Encaixe as 8 figuras pelo pé", [
        "Dentro da casa: Maria à esquerda, Jesus na manjedoura no meio (mais à frente) e José à direita.",
        "Na frente da casa: Melchior, Baltazar e Gaspar (os 3 Reis Magos); a ovelha no canto da frente esquerdo.",
        "A palmeira fica do lado de fora, à esquerda da casa.",
        "O lado gravado (rosto e roupa) sempre para a FRENTE.",
        "Os rasgos das figuras são todos iguais (16 mm): se trocar uma de lugar, ela encaixa igual — use o mapa "
        "para ficar como no projeto."])
    larg = LARG / 8
    for i, k in enumerate(FIGURAS):
        peca(pg, pc, k, M + i * larg, y, larg - 3, 28, rotulo=True)


def pagina_telhado(pg, pc):
    y = cabecalho(pg, 6, "Passo 4 — telhado", "Por último. Cada placa tem 2 rasgos que encaixam no topo da fachada e "
                  "do fundo.")
    peca(pg, pc, "T01", M + 10, y + 2, 70, 70, destaque=True)
    peca(pg, pc, "F01", M + 95, y + 10, LARG - 100, 60)
    seta(pg, M + 55, y + 34, M + 115, y + 22)
    y += 84
    y = passo(pg, y, 4, "Primeira água (T01, esquerda)", [
        "A borda de 156 mm MAIS LONGE dos rasgos é a cumeeira (o alto do telhado).",
        "Apoie essa borda no topo da fachada e do fundo e baixe a placa até os 2 rasgos entrarem nas linguetas "
        "inclinadas das empenas (os dentinhos do telhado da fachada e do fundo).",
        "O lado com a textura de telhas fica para FORA (para cima)."])
    y = passo(pg, y, 5, "Segunda água (T02, direita)", [
        "Igual à primeira, do outro lado.",
        "No alto fica uma pequena fresta em V entre as duas placas: é normal (o corte é reto)."])
    caixa(pg, y, "Para deixar fixo", "Depois de tudo encaixado a seco, se quiser, ponha uma gota de cola em cada "
          "encaixe com um palito. Para desmontar (sem cola), faça na ordem contrária: telhado, figuras, fachada e "
          "fundo, laterais.")


def pagina_problemas(pg, pc):
    y = cabecalho(pg, 7, "Problemas e soluções")
    for titulo, txt in (
            ("Encaixe muito apertado", "Lixe a lingueta de leve (lixa 220), 2 ou 3 passadas, e teste de novo. Nunca "
             "martele: o MDF racha no canto do rasgo."),
            ("Encaixe frouxo, a peça balança", "O MDF está mais fino que 3 mm. Uma gota de cola no encaixe resolve. "
             "Para o próximo, diminua a largura dos rasgos no programa (veja o teste do G01)."),
            ("Peça não soltou da chapa", "Não puxe: corte o ponto preso com estilete. Na próxima, confira o foco e "
             "a potência (corte 650 mm/min, 85 %, 2 passadas)."),
            ("Fumaça marcou a madeira", "Lixe de leve ou passe um pano úmido com álcool antes de montar."),
            ("Gravação das figuras fraca", "Aumente a potência da camada de gravação aos poucos (o projeto usa 35 % a "
             "2000 mm/min; nunca passe de 85 %) e teste num retalho."),
            ("Telhado não assenta", "Confira se a fachada e o fundo desceram até o fim nas laterais: se ficaram "
             "altos, as linguetas do telhado não alinham.")):
        y = caixa(pg, y, titulo, txt, VERM if "não" in titulo.lower() else VERDE)
    pg.texto(M, y + 4, LARG, "Projeto: PDF \"Presépio MDF 3 mm, revisão 02\" (peças e medidas). Chapas reencaixadas e "
             "manual: RedBlack Laser.", 7.5, False, CINZA)


def gerar(pdf_entrada, saida):
    pc = pr.limpar(pr.ler(pdf_entrada))
    pdf = QPdfWriter(saida)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle("Presépio — manual de montagem")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    pg = Pagina(pdf, p)
    paginas = (pagina_capa, pagina_pecas, pagina_teste, pagina_casa, pagina_figuras, pagina_telhado,
               pagina_problemas)
    assert len(paginas) == TOTAL
    for i, f in enumerate(paginas):
        if i:
            pg.nova()
        f(pg, pc)
    p.end()
    return saida


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print(gerar(sys.argv[1], sys.argv[2]))
