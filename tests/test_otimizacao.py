"""Otimização da ordem de corte: furos antes do contorno; vizinho mais próximo."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesa_dos_testes  # noqa: E402,F401  (mesa 400 x 400 dos testes)

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import percurso as pc  # noqa: E402

app = QApplication.instance() or QApplication([])


def snap(r, kind="rect"):
    p = fm.rect_path(QRectF(*r)) if kind == "rect" else fm.ellipse_path(QRectF(*r))
    return (p, QTransform(), "x", "C01", "#fff", None)


def larguras(p):
    out = []
    for t in p.trechos:
        if t.tipo == "corte":
            xs = [q[0] for q in t.pontos]
            out.append(round(max(xs) - min(xs), 3))
    return out


class OtimizacaoTest(unittest.TestCase):
    def test_furo_antes_do_contorno(self):
        snaps = [snap((0, 0, 100, 60)), snap((20, 20, 10, 10), "ellipse"), snap((60, 20, 10, 10))]
        c = [cm.nova("C01")]
        self.assertEqual(larguras(pc.gerar(snaps, c)), [10, 10, 100])        # furos primeiro, contorno por último
        self.assertEqual(larguras(pc.gerar(snaps, c, internas_primeiro=False)), [100, 10, 10])  # ordem da lista

    def test_vizinho_mais_proximo(self):
        snaps = [snap((300, 0, 10, 10)), snap((0, 380, 10, 10)), snap((150, 200, 10, 10))]
        p = pc.gerar(snaps, [cm.nova("C01")], vizinho=True)                  # parte da origem (0, 400)
        primeiros = [t.pontos[0] for t in p.trechos if t.tipo == "corte"]
        self.assertEqual([round(x) for x, _ in primeiros], [0, 150, 300])
        self.assertEqual(primeiros[0], (0.0, 390.0))                          # vértice mais perto da origem
        sem = pc.gerar(snaps, [cm.nova("C01")])
        self.assertLess(p.comprimento_vazio, sem.comprimento_vazio)

    def test_contornos_iguais_nao_se_contem(self):
        out = pc.ordenar_contornos([[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]] * 2, (0, 0))
        self.assertEqual(len(out), 2)



class SobrepostasTest(unittest.TestCase):
    def test_lado_comum_cortado_uma_vez(self):
        snaps = [snap((0, 0, 10, 10)), snap((10, 0, 10, 10))]                # lado x = 10 em comum
        c = [cm.nova("C01")]
        self.assertAlmostEqual(pc.gerar(snaps, c).comprimento_corte, 80, 6)
        self.assertAlmostEqual(pc.gerar(snaps, c, remover_sobrepostas=True).comprimento_corte, 70, 6)
        out = pc.sem_sobrepostas([[(0, 0), (5, 0), (5, 5)], [(5, 5), (5, 0), (9, 0)]])
        self.assertEqual(out, [[(0, 0), (5, 0), (5, 5)], [(5, 0), (9, 0)]])



def _bruta(linhas, pos, internas_primeiro=True, vizinho=False):
    """Referência simples (todos contra todos) para conferir a versão com índice espacial."""
    linhas = [list(x) for x in linhas]
    if internas_primeiro and len(linhas) > 1:
        cx = [(min(p[0] for p in ln), min(p[1] for p in ln), max(p[0] for p in ln), max(p[1] for p in ln))
              for ln in linhas]
        niv = [sum(1 for j, ln in enumerate(linhas) if j != i and pc._fechada(ln) and cx[j][0] <= cx[i][0]
                   and cx[j][1] <= cx[i][1] and cx[j][2] >= cx[i][2] and cx[j][3] >= cx[i][3]
                   and (cx[j] != cx[i] or j < i) and pc._dentro(linhas[i][0], ln)) for i in range(len(linhas))]
        grupos = {}
        for i in sorted(range(len(linhas)), key=lambda i: -niv[i]):
            grupos.setdefault(niv[i], []).append(i)
        grupos = [grupos[k] for k in sorted(grupos, reverse=True)]
    else:
        grupos = [list(range(len(linhas)))]
    if not vizinho:
        return [linhas[i] for g in grupos for i in g]
    out = []
    for g in grupos:
        resto = list(g)
        while resto:
            cand = sorted(((pc._melhor_inicio(linhas[i], pos), i) for i in resto), key=lambda t: (t[0][0], t[1]))
            (d, feita), i = cand[0]
            resto.remove(i)
            out.append(feita)
            pos = feita[-1]
    return out


class IndiceEspacialTest(unittest.TestCase):
    def test_igual_a_forca_bruta(self):
        import random
        rnd = random.Random(7)
        for _ in range(40):
            linhas = []
            for _k in range(rnd.randint(2, 50)):
                x, y, w = rnd.uniform(0, 300), rnd.uniform(0, 300), rnd.uniform(1, 80)
                if rnd.random() < 0.2:
                    linhas.append([(x, y), (x + w, y + rnd.uniform(-5, 5))])
                else:
                    linhas.append([(x, y), (x + w, y), (x + w, y + w), (x, y + w), (x, y)])
            pos = (rnd.uniform(0, 300), rnd.uniform(0, 300))
            for kw in ({"internas_primeiro": True}, {"internas_primeiro": True, "vizinho": True},
                       {"internas_primeiro": False, "vizinho": True}):
                self.assertEqual(pc.ordenar_contornos(linhas, pos, **kw), _bruta(linhas, pos, **kw))


if __name__ == "__main__":
    unittest.main()
