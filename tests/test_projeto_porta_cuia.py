"""Projeto Porta-cuia e térmica: medidas das peças conferidas com o PDF e G-code válido em todas as abas."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tools", "projetos"))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import porta_cuia_termica as pc_proj  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import geometria as g  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])

# envoltória (largura × altura) e número de furos/rasgos (pranchas 3, 5, 6, 7, 8, 9)
ESPERADO = {"P01": ((310, 170), 0), "P02": ((310, 170), 13), "P03": ((150, 334), 5), "P04": ((302, 83), 0),
            "P05": ((150, 66), 0), "P06": ((151, 150), 5), "P07": ((151, 54), 0), "P08": ((134, 134), 1)}


def caixa(path):
    r = path.boundingRect()
    return round(r.width(), 2), round(r.height(), 2)


class PortaCuiaTest(unittest.TestCase):
    def test_pecas_conferem_com_o_pdf(self):
        vistos = {}
        for _, pecas in pc_proj.FOLHAS:
            for partes, nome, _, _ in pecas:
                cod = nome[:3]
                if cod not in ESPERADO:
                    continue
                contorno = [p for p, lid in partes if lid == "C01"]
                self.assertEqual(len(contorno), 1, nome)
                self.assertEqual(caixa(contorno[0]), ESPERADO[cod][0], nome)
                self.assertEqual(sum(lid == "C02" for _, lid in partes), ESPERADO[cod][1], nome)
                for f, lid in partes:  # todo furo dentro do contorno
                    if lid == "C02":
                        self.assertTrue(contorno[0].contains(f.boundingRect().center()), nome)
                vistos[cod] = vistos.get(cod, 0) + 1
        self.assertEqual(vistos, {"P01": 1, "P02": 1, "P03": 2, "P04": 2, "P05": 2, "P06": 1, "P07": 2, "P08": 1})
        self.assertEqual(sum(vistos.values()), 12)  # "Total 12" da lista de peças

    def test_cotas_de_furos(self):
        p02 = dict((round(f.boundingRect().x(), 3), f) for f, lid in pc_proj.p02() if lid == "C02")
        self.assertIn(148.925, p02)  # A
        r = pc_proj.p06()[0][0].boundingRect()  # furo da cuia
        self.assertEqual((round(r.center().x(), 3), round(r.center().y(), 3), round(r.width(), 3)), (69.5, 75, 82))
        anel = [caixa(p) for p, _ in pc_proj.p08()]
        self.assertEqual(anel, [(120, 120), (134, 134)])

    def test_abas_e_gcode_em_mesa_370x360(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = pc_proj.gerar(os.path.join(tmp, "porta_cuia.rbl"))
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            w.show_info = w.show_error = lambda *a: None
            try:
                g.definir_mesa(370, 360)  # área de referência da S30 Pro Max citada no PDF
                self.assertTrue(w.open_path(arq))
                self.assertEqual(w.nomes_paginas, [n for n, _ in pc_proj.FOLHAS])
                self.assertIn("MONTAGEM", w.notas)
                for i in range(len(w.paginas)):
                    w.ir_para_pagina(i)
                    r = ob.bounds(w.canvas.view.shapes())
                    self.assertTrue(r.left() >= 0 and r.top() >= 0 and r.right() <= 370 and r.bottom() <= 360,
                                    (w.nomes_paginas[i], r))
                    destino = os.path.join(tmp, f"folha{i}.gcode")
                    self.assertTrue(w.export_gcode_to(destino), w.nomes_paginas[i])
                    with open(destino, encoding="utf-8") as f:
                        txt = f.read()
                    info = gc.analisar(txt)
                    self.assertTrue(info["dentro_da_area"] and info["fim_desligado"])
                    if "; Camada C02" in txt:  # a folha 03 (paredes e costelas) não tem furos
                        self.assertLess(txt.index("; Camada C02"), txt.index("; Camada C01"))  # furos primeiro
                    self.assertIn("; Camada C01", txt)
            finally:
                g.definir_mesa(400, 400)
                w.close()


def furos(partes):
    return [p.boundingRect() for p, lid in partes if lid == "C02"]


def abas_embaixo(partes, t):
    """Centros X das linguetas de baixo (Y de 0 a t) do contorno."""
    cont = next(p for p, lid in partes if lid == "C01")
    xs = sorted({round(cont.elementAt(i).x, 6) for i in range(cont.elementCount())
                 if abs(cont.elementAt(i).y) < 1e-9})
    return [round((a + b) / 2, 6) for a, b in zip(xs[::2], xs[1::2])]


class TresMilimetrosTest(unittest.TestCase):
    def setUp(self):
        self.p = pc_proj.Projeto(3.0)

    def test_envoltorias(self):
        p = self.p
        esperado = {"p01": (310, 170), "p02": (310, 170), "p03": (156, 337), "p04": (302, 80), "p05": (156, 63),
                    "p06": (151, 156), "p07": (151, 51), "p08": (134, 134)}
        for nome, wh in esperado.items():
            cont = next(q for q, lid in getattr(p, nome)() if lid == "C01")
            self.assertEqual(caixa(cont), wh, nome)

    def test_rasgos_para_3mm(self):
        rs = furos(self.p.p02())
        larg = sorted({(round(r.width(), 3), round(r.height(), 3)) for r in rs})
        self.assertEqual(larg, [(3.15, 26.15), (6.15, 24.15), (28.15, 3.15)])  # C, A (duas lâminas), B
        um, dois = self.p.larguras_teste()
        self.assertEqual((um, dois), ([2.7, 2.85, 3.0, 3.15, 3.3], [5.7, 5.85, 6.0, 6.15, 6.3]))

    def test_machos_caem_nos_rasgos(self):
        p, t = self.p, 3.0
        y0 = p.y0
        # divisória no piso: machos A (centros absolutos) = rasgos A do piso
        a = [c + y0 for c in abas_embaixo(p.p03(), t)]
        rasgos_a = sorted(round(r.center().y(), 6) for r in furos(p.p02()) if round(r.width(), 2) == 6.15)
        self.assertEqual(sorted(a), rasgos_a)
        # bandeja na divisória: rasgos D da P03 (X) = machos D da P06 (Y)
        d_p03 = sorted(round(r.center().x(), 6) for r in furos(p.p03())[1:] if round(r.width(), 2) == 28.15)
        cont6 = next(q for q, lid in p.p06() if lid == "C01")
        ys_d = sorted({round(cont6.elementAt(i).y, 6) for i in range(cont6.elementCount())
                       if cont6.elementAt(i).x > p.corpo + 1})
        self.assertEqual(d_p03, [round((ys_d[0] + ys_d[1]) / 2, 6), round((ys_d[2] + ys_d[3]) / 2, 6)])
        # costelas: rasgos F da P03 (X) = rasgos E da P06 (Y) = posições das costelas
        f_p03 = sorted(round(r.center().x(), 6) for r in furos(p.p03()) if round(r.width(), 2) == 3.15)
        e_p06 = sorted({round(r.center().y(), 6) for r in furos(p.p06()) if round(r.width(), 2) == 22.15})
        self.assertEqual(f_p03, e_p06)
        # machos E da costela = rasgos E da bandeja (X)
        e_x = sorted({round(r.center().x(), 6) for r in furos(p.p06()) if round(r.width(), 2) == 22.15})
        self.assertEqual(sorted(abas_embaixo(p.p07(), t)), e_x)
        # alturas: topo a 340 mm da mesa; furo da cuia no lugar do PDF
        self.assertEqual(caixa(next(q for q, lid in p.p03() if lid == "C01"))[1] + t, 340)
        r = furos(p.p06())[0]
        self.assertEqual((round(r.center().x() + y0, 3), round(r.center().y() + y0, 3), round(r.width(), 3)),
                         (79.5, 85, 82))

    def test_seis_mm_igual_ao_pdf(self):
        p6 = pc_proj.Projeto(6.0)
        d = sorted((round(r.x(), 3), round(r.y(), 3)) for r in furos(p6.p03())[1:])
        self.assertEqual(d, [(5.925, 165.925), (31.925, 147.925), (89.925, 147.925), (137.925, 165.925)])
        e = sorted((round(r.x(), 3), round(r.y(), 3)) for r in furos(p6.p06())[1:])
        self.assertEqual(e, [(19.925, 5.925), (19.925, 137.925), (89.925, 5.925), (89.925, 137.925)])
        self.assertEqual(abas_embaixo(p6.p05(), 6), [37.5, 112.5])

    def test_arquivo_3mm_em_mesa_370x360(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = pc_proj.gerar(os.path.join(tmp, "p3.rbl"), 3.0)
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            w.show_info = w.show_error = lambda *a: None
            try:
                g.definir_mesa(370, 360)
                self.assertTrue(w.open_path(arq))
                self.assertEqual([c.passadas for c in w.layers], [1, 1])
                for i in range(len(w.paginas)):
                    w.ir_para_pagina(i)
                    r = ob.bounds(w.canvas.view.shapes())
                    self.assertTrue(r.right() <= 370 and r.bottom() <= 360, (w.nomes_paginas[i], r))
                    self.assertTrue(w.export_gcode_to(os.path.join(tmp, f"f{i}.gcode")), w.nomes_paginas[i])
            finally:
                g.definir_mesa(400, 400)
                w.close()


class MontagemNoPisoTest(unittest.TestCase):
    """Põe cada parede no lugar sobre o piso e confere: toda lingueta cai num rasgo e todo rasgo recebe uma."""

    def checar(self, t):
        P = pc_proj.Projeto(t)

        def abas(partes):
            c = next(q for q, lid in partes if lid == "C01")
            xs = sorted({round(c.elementAt(i).x, 6) for i in range(c.elementCount()) if abs(c.elementAt(i).y) < 1e-9})
            return list(zip(xs[::2], xs[1::2]))
        rasgos = [q.boundingRect() for q, lid in P.p02() if lid == "C02"]
        pegadas = [(a + 4, y0, b + 4, y0 + t) for a, b in abas(P.p04()) for y0 in (4, 166 - t)]          # P04
        pegadas += [(x0, a + P.y0, x0 + t, b + P.y0) for a, b in abas(P.p05()) for x0 in (4, 306 - t)]  # P05
        pegadas += [(155 - t, a + P.y0, 155 + t, b + P.y0) for a, b in abas(P.p03())]                    # P03 dupla
        usados = set()
        for x1, y1, x2, y2 in pegadas:
            dentro = [i for i, r in enumerate(rasgos) if r.left() <= x1 + 1e-6 and r.top() <= y1 + 1e-6
                      and x2 <= r.right() + 1e-6 and y2 <= r.bottom() + 1e-6]
            self.assertEqual(len(dentro), 1, (t, x1, y1, x2, y2))
            r = rasgos[dentro[0]]
            self.assertAlmostEqual(min(x1 - r.left(), r.right() - x2, y1 - r.top(), r.bottom() - y2), P.f / 2,
                                   places=6)  # folga igual dos dois lados
            usados.add(dentro[0])
        self.assertEqual((len(pegadas), len(usados), len(rasgos)), (13, 13, 13))
        # cantos: as pontas (P05) cabem entre as paredes longas e têm a mesma altura das pontas de P04
        self.assertAlmostEqual(P.y0 + P.interno, 166 - t, places=6)
        alt = lambda partes: caixa(next(q for q, lid in partes if lid == "C01"))[1]  # noqa: E731
        self.assertEqual(alt(P.p05()), 60 + t)

    def test_3mm(self):
        self.checar(3.0)

    def test_6mm(self):
        self.checar(6.0)


if __name__ == "__main__":
    unittest.main()
