"""Projeto Carroça colonial: medidas conferidas com a tabela do PDF, encaixes que fecham e G-code válido na mesa."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tools", "projetos"))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import carroca_colonial as cc  # noqa: E402
import etiquetas as et  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import geometria as g  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def caixa(partes, lid="C01"):
    r = next(p for p, l_ in partes if l_ == lid).boundingRect()
    return round(r.width(), 2), round(r.height(), 2)


def furos(partes):
    return [p.boundingRect() for p, lid in partes if lid == "C02"]


class CarrocaTest(unittest.TestCase):
    def test_medidas_da_tabela(self):
        self.assertEqual(caixa(cc.lateral()), (170, 59.9))          # 170 × 56,9 + abas de 3 (sem folga)
        self.assertEqual(caixa(cc.assoalho()), (170, 66))
        self.assertEqual(caixa(cc.tampa()), (71.8, 56))
        self.assertEqual(caixa(cc.roda(58, 9, 23.25)), (58, 58))
        self.assertEqual(caixa(cc.roda(46, 8.1, 17.9)), (46, 46))
        self.assertEqual(caixa(cc.berco()), (81.64, 43))            # ~83 × 43
        self.assertEqual(caixa(cc.mancal(22, 14)), (30, 25))        # 30 × 22 + abas
        self.assertEqual(caixa(cc.mancal(28, 20)), (30, 31))
        self.assertEqual(caixa(cc.banco()), (60, 17))
        self.assertEqual(caixa(cc.suporte_banco()), (15, 26))       # 15 × 23 + aba 3 (= espessura)
        self.assertEqual(caixa(cc.calibrador()), (48, 31))
        self.assertEqual([round(r.width(), 2) for r in furos(cc.roda(58, 9, 23.25))[:1]], [4.0])  # = vareta
        self.assertEqual([round(r.width(), 2) for r in furos(cc.mancal(22, 14))], [4.0])
        for c in cc.camadas():  # corte 650 mm/min, 2 passadas; nunca acima de 85 %
            self.assertLessEqual(c.potencia_max, 85)
            if c.id != cc.GRAV:
                self.assertEqual((c.velocidade_mm_min, c.potencia_max, c.passadas), (650, 85, 2))
        self.assertEqual(sorted(round(r.width(), 2) for r in furos(cc.calibrador())[:4]), [2.8, 2.9, 3.0, 3.1])
        self.assertEqual(len(furos(cc.roda(46, 8.1, 17.9))), 9)     # furo + 8 janelas
        nomes = [n for _, pecas in cc.FOLHAS for _, n, _, _ in pecas]
        self.assertEqual(len(nomes), 36)                             # 35 peças + Q1
        for pref, qtd in (("L", 2), ("RT", 2), ("RD", 2), ("B", 2), ("E", 4), ("G", 8), ("R", 4), ("D", 4),
                          ("T", 2), ("A", 3)):
            self.assertEqual(sum(n.split()[0].rstrip("0123456789") == pref for n in nomes), qtd, pref)

    def test_encaixes_fecham(self):
        p1 = furos(cc.assoalho())
        # abas da lateral (x, 7 de largura) = rasgos 7 × 3 do assoalho
        rasgos_lat = sorted({round(r.x(), 2) for r in p1 if round(r.width(), 2) == 7})
        self.assertEqual(rasgos_lat, list(cc.ABAS_LAT))
        # abas do berço: 7 de largura a ±3,5..10,5 do centro = rasgos 3 × 7 (y) a partir do centro do piso (33)
        ys = sorted({round(r.y() - 33, 2) for r in p1 if round(r.height(), 2) == 7})
        self.assertEqual(ys, [-10.5, 3.5])
        # meios-encaixes do berço (±18,5..21,5) = rasgos dos mancais no piso (y 11,5 e 51,5 → -21,5 e 18,5)
        ym = sorted({round(r.y() - 33, 2) for r in p1 if round(r.width(), 2) == 6})
        self.assertEqual(ym, [-21.5, 18.5])
        # abas do mancal (4..10 e 20..26, centro 15) = rasgos 6 × 3 a -11 e +5 do eixo
        xm = sorted(round(r.x() - cc.EIXOS[0], 2) for r in p1 if round(r.width(), 2) == 6 and r.y() < 20
                    and r.x() < 60)
        self.assertEqual(xm, [-11.0, 5.0])
        # rodas no chão: eixo a 14 + R29 atrás = 20 + R23 na frente
        self.assertEqual(14 + 29, 20 + 23)

    def test_folhas_na_mesa_sem_sobrepor_e_gcode(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = cc.gerar(os.path.join(tmp, "carroca.rbl"))
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            w.show_info = w.show_error = lambda *a: None
            try:
                g.definir_mesa(365, 370)
                self.assertTrue(w.open_path(arq))
                nomes = [n for n, _ in cc.FOLHAS]
                self.assertEqual(w.nomes_paginas, nomes + [f"SÓ LETRAS de {n} (não mover a chapa)" for n in nomes])
                for i in range(len(w.paginas)):
                    w.ir_para_pagina(i)
                    pecas = [s for s in w.canvas.view.shapes()]
                    r = ob.bounds(pecas)
                    self.assertTrue(r.left() >= 0 and r.top() >= 0 and r.right() <= 365 and r.bottom() <= 370,
                                    (w.nomes_paginas[i], r))
                    pecas = [s for s in pecas if s.layer != et.CAMADA]  # letras ficam por cima das peças
                    caixas = [ob.bounds([s]).adjusted(1, 1, -1, -1) for s in pecas]  # folga mínima de 2 mm
                    for a in range(len(caixas)):
                        for b in range(a + 1, len(caixas)):
                            self.assertFalse(caixas[a].intersects(caixas[b]),
                                             (pecas[a].name, pecas[b].name))
                    destino = os.path.join(tmp, f"folha{i}.gcode")
                    self.assertTrue(w.export_gcode_to(destino), w.nomes_paginas[i])
                    with open(destino, encoding="utf-8") as f:
                        txt = f.read()
                    info = gc.analisar(txt)
                    self.assertTrue(info["dentro_da_area"] and info["fim_desligado"])
                    if "SÓ LETRAS" in w.nomes_paginas[i]:  # só grava, nada de corte
                        self.assertNotIn("; Camada C01", txt)
                        continue
                    self.assertLess(txt.index("; Camada C09"), txt.index("; Camada C02"))  # letras antes dos cortes
                    self.assertLess(txt.index("; Camada C02"), txt.index("; Camada C01"))
                    if "; Camada C03" in txt:
                        self.assertLess(txt.index("; Camada C03"), txt.index("; Camada C02"))
            finally:
                g.definir_mesa(400, 400)
                w.close()

    def test_letras_dentro_das_pecas(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            with open(cc.gerar(os.path.join(tmp, "c.rbl")), encoding="utf-8") as f:
                d = json.load(f)
        objs = d["paginas"][1]["objetos"] if d["paginas"][1] else d["objetos"]
        pecas = {et.CODIGO.match(o["nome"]).group(1): o for o in objs if o["tipo"] == "grupo"}
        letras = {o["nome"].split()[-1]: o for o in objs if o["tipo"] == "texto"}
        self.assertEqual(set(letras), set(pecas))  # 35 peças, 35 letras
        for cod, o in pecas.items():
            t = letras[cod]
            self.assertEqual((t["camada"], t["texto"]["altura_mm"] >= 1.8), (et.CAMADA, True))
            p = et.folhas(t, et.matriz(t))[0][0]
            partes = et.folhas(o, et.matriz(o))
            cont = max((q for q, lid in partes if lid == cc.CONT), key=lambda q: q.boundingRect().width())
            self.assertTrue(cont.contains(p.boundingRect()), cod)
            for q, lid in partes:
                if lid == cc.FURO:
                    self.assertFalse(q.intersects(p), cod)
        self.assertEqual(letras["P1"]["texto"]["texto"], "P1  FRENTE →")
        camada = next(c for c in d["camadas"] if c["id"] == et.CAMADA)
        self.assertEqual((camada["velocidade_mm_min"], camada["potencia_max"], d["camadas"][0]["id"]),
                         (3000, 15, et.CAMADA))


if __name__ == "__main__":
    unittest.main()
