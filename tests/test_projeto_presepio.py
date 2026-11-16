"""Presépio: 17 peças do PDF com as medidas da tabela, encaixe nas chapas com 2 mm, peça em vazado corta antes."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tools", "projetos"))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
PDF = r"F:\Downloads\Presepio_MDF_3mm_Projeto_Completo.pdf"
TABELA = {"B01": (350, 230), "F01": (250, 188), "L01": (160, 123), "T01": (150, 156), "P08": (90.1, 170.3),
          "G01": (125, 28)}


@unittest.skipUnless(os.path.exists(PDF), "PDF do presépio não está neste PC")
class PresepioTest(unittest.TestCase):
    def test_pecas_encaixe_e_ordem(self):
        import presepio as pr
        from redblack import projeto as pj
        pecas = pr.limpar(pr.ler(PDF))
        self.assertEqual(len(pecas), 17)
        for k, (w, h) in TABELA.items():
            r = pecas[k]["cont"].boundingRect()
            self.assertAlmostEqual(r.width(), w, delta=0.2, msg=k)
            self.assertAlmostEqual(r.height(), h, delta=0.2, msg=k)
        jose = pecas["P03"]["partes"]  # rosto desenhado (o PDF não tem) e sem o furinho de 0,7 mm na boca
        self.assertEqual(sum(t == "cheio" for _p, t in jose), 2)
        self.assertTrue(all(max(p.boundingRect().width(), p.boundingRect().height()) >= 1 for p, t in jose
                            if t == "furo"))
        for p, t in pecas["T01"]["partes"]:  # textura do telhado não passa do contorno
            if t == "linha":
                self.assertTrue(pecas["T01"]["cont"].boundingRect().contains(p.boundingRect()))
        saida = os.path.join(tempfile.mkdtemp(), "p.rbl")
        _s, ap, nomes, dentro, chapas = pr.gerar(PDF, saida)
        self.assertEqual(len(chapas), 3)
        self.assertTrue(dentro)  # aproveita os vazados
        for chapa in chapas:  # 2 mm entre contornos (com os vazados livres)
            for i, (a, pa, _da) in enumerate(chapa):
                for b, pb, _db in chapa[i + 1:]:
                    ca = next(p for p, _l, t in pa if t == "cont")
                    cb = next(p for p, _l, t in pb if t == "cont")
                    if ca.boundingRect().intersects(cb.boundingRect()):
                        self.assertFalse(_perto(ca, cb, pr.VAO - 0.6), (a, b))
        ordem = [c[0] for c in pr.CAMADAS]  # peça dentro de vazado corta antes do vazado
        self.assertLess(ordem.index(pr.CONT_DENTRO), ordem.index(pr.FURO))
        pj.load(saida)  # abre sem erro (nomes de aba, camadas)
        import json
        with open(saida, encoding="utf-8") as f:
            d = json.load(f)
        self.assertFalse(next(c for c in d["camadas"] if c["id"] == "C09")["saida"])  # peças sem marcação
        self.assertFalse(any(n.startswith("SÓ LETRAS") for n in d["nomes_paginas"]))
        # abas MARCA: só os contornos, nas mesmas posições da chapa de corte, camada 6000 mm/min a 80 %
        marca = next(c for c in d["camadas"] if c["id"] == pr.MARCA)
        self.assertEqual((marca["velocidade_mm_min"], marca["potencia_max"], marca["passadas"]), (6000, 80, 1))
        self.assertEqual(d["nomes_paginas"][3:], [f"MARCA p/ pintar — chapa {i}" for i in (1, 2, 3)])
        for i, chapa in enumerate(chapas):
            contornos = sorted((round(p.boundingRect().x(), 3), round(p.boundingRect().y(), 3))
                               for _k, partes, _d in chapa for p, _l, t in partes if t == "cont")
            objs = d["paginas"][3 + i]["objetos"]
            self.assertEqual(len(objs), len(contornos))
            self.assertTrue(all(o["camada"] == pr.MARCA for o in objs))
        import presepio_pintura as pp  # guia de pintura: só as 6 cores que o dono tem (+ sem tinta)
        self.assertLessEqual(set(pp.COR.values()), {"Azul", "Verde", "Amarelo", "Marrom", "Vermelho", "Rosa",
                                                     "Sem tinta"})
        self.assertEqual(set(pp.COR), set(pecas))
        guia = pp.gerar(PDF, os.path.join(tempfile.mkdtemp(), "pintura.pdf"))
        with open(guia, "rb") as f:
            self.assertTrue(f.read(5).startswith(b"%PDF"))
        import presepio_manual as pm
        man = pm.gerar(PDF, os.path.join(tempfile.mkdtemp(), "m.pdf"))
        with open(man, "rb") as f:
            self.assertTrue(f.read(5).startswith(b"%PDF"))


def _perto(a, b, d):
    from PySide6.QtGui import QPainterPathStroker
    st = QPainterPathStroker()
    st.setWidth(d)
    return st.createStroke(a).intersects(st.createStroke(b))


if __name__ == "__main__":
    unittest.main()
