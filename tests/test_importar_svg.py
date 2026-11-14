"""Etapa 5: unidade, escala e transformações testadas; elementos sem suporte sinalizados."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))  # offscreen não vê fontes do sistema
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import importar_svg as svg  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
NS = 'xmlns="http://www.w3.org/2000/svg"'
MM = f'<svg {NS} width="100mm" height="100mm" viewBox="0 0 100 100">{{}}</svg>'  # 1 unidade = 1 mm


def boxes(text):
    return [p.boundingRect().getRect() for _, p in svg.parse_svg(text).objetos]


class Base(unittest.TestCase):
    def assertBox(self, got, exp, tol=1e-6):
        for a, b in zip(got, exp):
            self.assertAlmostEqual(a, b, delta=tol, msg=f"{got} != {exp}")


class UnidadesEscalaTest(Base):
    def test_viewbox_escala(self):
        t = f'<svg {NS} width="100mm" height="50mm" viewBox="0 0 200 100"><rect x="20" y="10" width="40" height="20"/></svg>'
        self.assertBox(boxes(t)[0], (10, 5, 20, 10))

    def test_unidades(self):
        cases = {
            f'<svg {NS} width="1in" height="1in"><rect width="96" height="96"/></svg>': 25.4,
            f'<svg {NS} width="72pt" height="72pt" viewBox="0 0 72 72"><rect width="72" height="72"/></svg>': 25.4,
            f'<svg {NS} width="10cm" height="10cm" viewBox="0 0 10 10"><rect width="1" height="1"/></svg>': 10,
            f'<svg {NS} width="6pc" height="6pc" viewBox="0 0 6 6"><rect width="6" height="6"/></svg>': 25.4,
            f'<svg {NS} viewBox="0 0 96 96"><rect width="96" height="96"/></svg>': 25.4,      # sem width: px
            f'<svg {NS} width="96" height="96"><rect width="96" height="96"/></svg>': 25.4,     # número puro: px
        }
        for text, w in cases.items():
            self.assertAlmostEqual(boxes(text)[0][2], w, delta=1e-9, msg=text)

    def test_preserve_aspect_ratio(self):
        meet = f'<svg {NS} width="100mm" height="50mm" viewBox="0 0 100 100"><rect width="100" height="100"/></svg>'
        self.assertBox(boxes(meet)[0], (25, 0, 50, 50))  # uniforme e centralizado
        none = meet.replace("<svg ", '<svg preserveAspectRatio="none" ')
        self.assertBox(boxes(none)[0], (0, 0, 100, 50))

    def test_viewbox_deslocado(self):
        t = f'<svg {NS} width="100mm" height="100mm" viewBox="10 10 100 100"><rect x="10" y="10" width="5" height="5"/></svg>'
        self.assertBox(boxes(t)[0], (0, 0, 5, 5))

    def test_largura_percentual_gera_aviso(self):
        res = svg.parse_svg(f'<svg {NS} width="100%" viewBox="0 0 96 96"><rect width="96" height="96"/></svg>')
        self.assertTrue(res.avisos)
        self.assertAlmostEqual(res.objetos[0][1].boundingRect().width(), 25.4)

    def test_coordenada_com_unidade_no_elemento(self):
        # 10mm dentro de um espaço em px continua sendo 10 mm físicos
        t = f'<svg {NS} viewBox="0 0 400 400" width="400px" height="400px"><rect width="10mm" height="1in"/></svg>'
        self.assertBox(boxes(t)[0], (0, 0, 10, 25.4), 1e-9)


class TransformacoesTest(Base):
    def one(self, inner):
        return boxes(MM.format(inner))[0]

    def test_aninhadas_e_ordem(self):
        self.assertBox(self.one('<g transform="translate(10,20) scale(2)"><rect width="5" height="5"/></g>'),
                       (10, 20, 10, 10))
        self.assertBox(self.one('<rect transform="translate(10,0) scale(2)" width="1" height="1"/>'), (10, 0, 2, 2))
        self.assertBox(self.one('<rect transform="scale(2) translate(10,0)" width="1" height="1"/>'), (20, 0, 2, 2))
        self.assertBox(self.one('<g transform="translate(5,5)"><g transform="translate(1,1)"><rect width="1" height="1"/></g></g>'),
                       (6, 6, 1, 1))

    def test_rotate_matrix_skew(self):
        self.assertBox(self.one('<rect transform="rotate(90)" width="10" height="5"/>'), (-5, 0, 5, 10))
        self.assertBox(self.one('<rect transform="rotate(90 5 5)" width="10" height="5"/>'), (5, 0, 5, 10))
        self.assertBox(self.one('<rect transform="matrix(1,0,0,1,3,4)" width="1" height="1"/>'), (3, 4, 1, 1))
        self.assertBox(self.one('<rect transform="skewX(45)" width="10" height="10"/>'), (0, 0, 20, 10))
        self.assertBox(self.one('<rect transform="skewY(45)" width="10" height="10"/>'), (0, 0, 10, 20))


class CaminhosTest(Base):
    def p(self, d):
        return svg.parse_path(d).boundingRect().getRect()

    def test_comandos_retos_absolutos_e_relativos(self):
        self.assertBox(self.p("M10 10 h20 v10 H10 Z"), (10, 10, 20, 10))
        self.assertBox(self.p("m10 10 l20 0 l0 10 z"), (10, 10, 20, 10))
        self.assertBox(self.p("M0 0 10 0 10 10"), (0, 0, 10, 10))  # lineto implícito
        self.assertBox(self.p("M0,0L10-5"), (0, -5, 10, 5))        # números colados

    def test_curvas_com_reflexo(self):
        self.assertBox(self.p("M0 0 C0 10 10 10 10 0 S20 -10 20 0"), (0, -7.5, 20, 15))
        self.assertBox(self.p("M0 0 Q5 10 10 0 T20 0"), (0, -5, 20, 10))

    def test_arcos(self):
        self.assertBox(self.p("M0 0 A10 10 0 0 1 20 0"), (0, -10, 20, 10), 1e-9)   # sweep=1: por cima
        self.assertBox(self.p("M0 0 A10 10 0 0 0 20 0"), (0, 0, 20, 10), 1e-9)     # sweep=0: por baixo
        self.assertBox(self.p("M0 0 A20 10 90 0 1 0 40"), (0, 0, 10, 40), 1e-9)    # elipse girada
        self.assertBox(self.p("M0 0 A1 1 0 0 1 20 0"), (0, -10, 20, 10), 1e-9)     # raio pequeno é ampliado
        self.assertEqual(self.p("M0 0 a10 10 0 0120 0"), self.p("M0 0 a10 10 0 0 1 20 0"))  # flags coladas
        full = svg.parse_path("M0 10 A10 10 0 1 1 20 10 A10 10 0 1 1 0 10")
        self.assertBox(full.boundingRect().getRect(), (0, 0, 20, 20), 1e-9)
        # ponto do meio do arco está no círculo (erro da aproximação cúbica < 0,03 % do raio)
        mid = svg.parse_path("M0 0 A10 10 0 0 1 20 0").pointAtPercent(0.25)
        r = ((mid.x() - 10) ** 2 + mid.y() ** 2) ** 0.5
        self.assertAlmostEqual(r, 10, delta=10 * 3e-4)

    def test_caminho_incompleto(self):
        with self.assertRaises(svg.SvgInvalido):
            svg.parse_path("M 10")


class ElementosTest(Base):
    def test_formas_basicas(self):
        t = MM.format('<circle cx="50" cy="50" r="10"/><ellipse cx="10" cy="20" rx="5" ry="3"/>'
                      '<line x1="0" y1="0" x2="10" y2="5"/><polyline points="0,0 10,0 10,10"/>'
                      '<polygon points="0 0 4 0 2 3"/><rect x="1" y="2" width="10" height="6" rx="2"/>')
        b = boxes(t)
        self.assertBox(b[0], (40, 40, 20, 20))
        self.assertBox(b[1], (5, 17, 10, 6))
        self.assertBox(b[2], (0, 0, 10, 5))
        self.assertBox(b[3], (0, 0, 10, 10))
        self.assertBox(b[4], (0, 0, 4, 3))
        self.assertBox(b[5], (1, 2, 10, 6))

    def test_sem_suporte_e_ocultos_sao_sinalizados(self):
        t = MM.format('<title>t</title><defs><linearGradient id="g"/></defs><style>.a{}</style>'
                      '<text>Olá</text><image href="x.png"/><use href="#r"/><rect id="r" width="1" height="1"/>'
                      '<rect display="none" width="1" height="1"/><rect style="fill:red; display: none" width="1" height="1"/>'
                      '<rect width="0" height="0"/>')
        res = svg.parse_svg(t)
        self.assertEqual([n for n, _ in res.objetos], ["r"])
        self.assertEqual(dict(res.ignorados), {"text": 1, "image": 1, "use": 1, "rect (oculto)": 2, "rect (vazio)": 1})

    def test_arquivos_rejeitados(self):
        bomb = ('<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]>'
                f'<svg {NS}><text>&b;</text></svg>')
        for bad in (bomb, "<svg", f'<html {NS}></html>'):
            with self.assertRaises(svg.SvgInvalido):
                svg.parse_svg(bad)

    def test_regra_de_preenchimento(self):
        from PySide6.QtCore import Qt
        res = svg.parse_svg(MM.format('<rect width="1" height="1"/><rect fill-rule="evenodd" width="1" height="1"/>'
                                      '<path style="fill-rule: evenodd" d="M0 0 H1 V1 Z"/>'))
        self.assertEqual([p.fillRule() for _, p in res.objetos], [Qt.WindingFill, Qt.OddEvenFill, Qt.OddEvenFill])

    def test_codificacao_declarada(self):
        data = (f'<?xml version="1.0" encoding="ISO-8859-1"?><svg {NS} width="10mm" height="10mm" viewBox="0 0 10 10">'
                '<rect id="ação" width="1" height="1"/></svg>').encode("latin-1")
        self.assertEqual(svg.parse_svg(data).objetos[0][0], "ação")


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(("erro", m))
        self.win.show_info = lambda t, m: self.msgs.append(("info", m))
        self.win.show()
        app.processEvents()
        self.view = self.win.canvas.view

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def write(self, text, name="a.svg"):
        p = os.path.join(self.tmp.name, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_importar_selecionar_desfazer(self):
        n = len(self.view.shapes())
        p = self.write(MM.format('<rect id="placa" x="10" y="20" width="30" height="15"/><text>x</text>'))
        self.assertTrue(self.win.import_path(p))
        self.assertEqual(len(self.view.shapes()), n + 1)
        sel = self.view.selected()
        self.assertEqual([s.name for s in sel], ["placa"])
        self.assertAlmostEqual(self.win.fields["w"].value(), 30)
        self.assertAlmostEqual(self.win.fields["h"].value(), 15)
        self.assertEqual(self.msgs[0][0], "info")
        self.assertIn("text: 1", self.msgs[0][1])
        self.assertEqual(self.win.undo_stack.undoText(), "Importar a.svg")
        self.win.undo_stack.undo()
        self.assertEqual(len(self.view.shapes()), n)

    def test_importar_invalido_nao_altera(self):
        n = len(self.view.shapes())
        self.assertFalse(self.win.import_path(self.write("<svg", "ruim.svg")))
        self.assertFalse(self.win.import_path(self.write(MM.format("<text>só texto</text>"), "vazio.svg")))
        self.assertEqual(len(self.view.shapes()), n)
        self.assertEqual([k for k, _ in self.msgs], ["erro", "erro"])
        self.assertEqual(self.win.undo_stack.count(), 0)

    def test_amostra_do_repositorio(self):
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "exemplos", "amostra.svg")
        self.assertTrue(self.win.import_path(p))
        names = {s.name for s in self.view.selected()}
        self.assertIn("moldura-100x60mm", names)
        frame = next(s for s in self.view.selected() if s.name == "moldura-100x60mm")
        r = frame.path().boundingRect()
        self.assertAlmostEqual(r.width(), 100, delta=1e-9)
        self.assertAlmostEqual(r.height(), 60, delta=1e-9)


if __name__ == "__main__":
    unittest.main()
