"""Suporte de mesa com carga USB-C para Ulefone Armor 27T (MDF 3 mm) — Suporte_Armor27T_Plano_de_Execucao.pdf.

Páginas 5 e 6 = chapas 1 e 2 em escala 1:1 (contornos vermelhos fechados = corte). As figuras ovais (Jesus com o
filho / com a filha) estão em vetor na página 5 e são gravadas por preenchimento nas faces EXTERNAS das laterais.
Peças conferidas pela lista de corte (pág. 2): laterais 110 × 198 (2 esquerdas + 2 direitas com rasgo), base
140 × 120, encosto 74 × 145, frente 86 × 55, 8 calços 18 × 28, 4 guias 20 × 9, lingueta 65 × 22, piso/teto 74 × 36.
Camadas na ordem do dono: C03 gravação (preenchimento 2000/35 %), C01 corte (630/85 %/2). Grave antes de cortar.

Executar:  python tools/projetos/suporte_armor27t.py [pdf] [saida.rbl]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from redblack import camadas as cm  # noqa: E402
from redblack import importar_pdf as pdfimp  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402

PDF = r"F:\Downloads\Suporte_Armor27T_Plano_de_Execucao.pdf"
# (largura, altura) da caixa -> (código, nome); laterais separadas pelo nº de vértices (a direita tem o rasgo)
TABELA = [((140, 120), "B", "Base aberta à direita"), ((74, 145), "E", "Encosto"), ((86, 55), "F", "Frente fechada"),
          ((18, 28), "K", "Calço para laminação"), ((20, 9), "G", "Guia da lingueta"),
          ((65, 22), "L", "Lingueta removível"), ((74, 36), "P", "Piso/teto do berço")]
ESPERADO = {"LE": 2, "LD": 2, "B": 1, "E": 1, "F": 1, "K": 8, "G": 4, "L": 1, "P": 2}


def _perto(a, b, tol=0.6):
    return abs(a - b) <= tol


def _fechado(p):
    q = p.toSubpathPolygons()
    return all((s.first() - s.last()).manhattanLength() < 0.05 for s in q)


def classificar(objetos):
    """[(código, nome, path de corte)] e [path de gravação] de uma página."""
    pecas, artes = [], []
    for _n, p in objetos:
        b = p.boundingRect()
        if p.elementCount() > 2000:          # figura oval em vetor (milhares de pontos) = gravação
            artes.append(p)
            continue
        if _perto(b.width(), 110) and _perto(b.height(), 198):
            com_rasgo = p.elementCount() > 20  # a lateral direita tem o rasgo arredondado embaixo
            pecas.append(("LD" if com_rasgo else "LE", "Lateral direita com rasgo" if com_rasgo else "Lateral esquerda", p))
            continue
        for (w, h), cod, nome in TABELA:
            if (_perto(b.width(), w) and _perto(b.height(), h)) or (_perto(b.width(), h) and _perto(b.height(), w)):
                pecas.append((cod, nome, p))
                break
        else:
            raise ValueError(f"peça não reconhecida: {b.width():.1f} × {b.height():.1f}")
    return pecas, artes


def montar(pdf=PDF):
    abas, contagem = [], {}
    for pag, nome_aba in ((4, "Chapa 1 — laterais, base, encosto, frente"), (5, "Chapa 2 — lateral, trava e berço")):
        res = pdfimp.load(pdf, pag)
        pecas, artes = classificar(res.objetos)
        snaps = []
        usadas = set()
        for cod, nome, p in pecas:
            assert _fechado(p), f"{nome}: contorno aberto"
            contagem[cod] = contagem.get(cod, 0) + 1
            itens = [ob.Shape(p, f"{nome} — corte", "C01", cm.cor("C01"))]
            for i, a in enumerate(artes):  # figura dentro desta lateral = face externa gravada
                if i not in usadas and cod in ("LE", "LD") and p.boundingRect().contains(a.boundingRect()):
                    itens.insert(0, ob.Shape(a, f"{nome} — gravação (face externa)", "C03", cm.cor("C03")))
                    usadas.add(i)
            g = ob.group(itens)
            g.name = f"{cod}{contagem[cod]} {nome}" + (" (face externa gravada)" if len(itens) > 1 else "")
            snaps.append(g.snapshot())
        assert len(usadas) == len(artes), "figura fora de uma lateral"
        abas.append((nome_aba, tuple(snaps)))
    assert contagem == ESPERADO, contagem
    return abas


def camadas():
    return [cm.alterar(cm.Camada("C03", "Gravação das figuras (preenchimento)"), modo="preenchimento",
                       velocidade_mm_min=2000.0, potencia_max=35.0, potencia_min=0.0, passadas=1, intervalo_mm=0.1,
                       air=True),
            cm.alterar(cm.Camada("C01", "Corte MDF 3 mm"), modo="linha", velocidade_mm_min=630.0, potencia_max=85.0,
                       potencia_min=0.0, passadas=2, air=True)]


NOTAS = """Suporte de mesa USB-C para Ulefone Armor 27T (PDF Suporte_Armor27T_Plano_de_Execucao). MDF 3 mm, 2 chapas.
Laterais: 2 peças coladas face a face de cada lado; só as faces externas têm a figura (Filho à esquerda, Filha à
direita). Piso/teto do berço e lingueta saem como retângulos: o U para o plugue é recortado depois de medir o cabo
real (pág. 4 do PDF)."""


def gerar(pdf=PDF, destino="Suporte_Armor27T_MDF_3mm_RedBlack.rbl"):
    abas = montar(pdf)
    pj.save(destino, abas[0][1], camadas(), notas=NOTAS, paginas=[None, (abas[1][1], (), ())], pagina_atual=0,
            nomes_paginas=[n for n, _ in abas])
    return destino, abas


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    a = sys.argv[1:]
    d, abas = gerar(a[0] if a else PDF, a[1] if len(a) > 1 else "Suporte_Armor27T_MDF_3mm_RedBlack.rbl")
    print(d)
    for n, s in abas:
        print(" ", n, ":", ", ".join(x[2] for x in s))
