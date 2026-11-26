"""Páginas: cada uma com seus objetos; camadas comuns; só a aberta vai para a prévia/G-code; salvas no projeto."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import camadas as cm  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class PaginasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.show_info = self.w.show_error = lambda *a: None

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def nomes(self):
        return sorted(s.name for s in self.w.canvas.view.shapes())

    def por_quadrado(self, nome, x=50):
        s = ob.Shape(fm.rect_path(QRectF(x, 50, 20, 20)), nome, "C02", cm.cor("C02"))
        self.w._edit("teste", lambda: self.w.canvas.scene.addItem(s))

    def test_adicionar_trocar_duplicar_excluir(self):
        demo = self.nomes()
        self.assertEqual(self.w.abas.count(), 1)
        self.assertTrue(self.w.adicionar_pagina())
        self.assertEqual((self.w.abas.count(), self.w.pagina_atual, self.nomes()), (2, 1, []))  # nova vazia
        self.por_quadrado("só na 2")
        self.assertTrue(self.w.ir_para_pagina(0))
        self.assertEqual(self.nomes(), demo)
        self.w.abas.setCurrentIndex(1)  # clicar na aba troca
        self.assertEqual(self.nomes(), ["só na 2"])
        self.assertTrue(self.w.adicionar_pagina(duplicar=True))
        self.assertEqual((self.w.pagina_atual, self.nomes()), (2, ["só na 2"]))
        self.assertEqual([self.w.abas.tabText(i) for i in range(3)], ["Página 1", "Página 2", "Página 2 (cópia)"])
        self.assertTrue(self.w.excluir_pagina())
        self.assertEqual((self.w.abas.count(), self.w.pagina_atual), (2, 1))
        self.w.ir_para_pagina(0)
        self.w.excluir_pagina()
        self.assertEqual(self.nomes(), ["só na 2"])
        self.assertFalse(self.w.excluir_pagina())  # fica pelo menos uma

    def test_marcar_feita_falta_e_automatico(self):
        from redblack import conexao as cx
        self.assertEqual(self.w.progresso_abas.text(), "")  # uma página, nada marcado: some
        self.w.adicionar_pagina()
        self.w.adicionar_pagina()
        self.assertTrue(self.w.marcar_pagina(0))
        self.assertFalse(self.w.marcar_pagina(0))  # já estava
        self.assertEqual(self.w.abas.tabText(0), "✓ Página 1")
        self.assertIn("Feitas 1 de 3", self.w.progresso_abas.text())
        self.assertIn("Falta: Página 2, Página 3", self.w.progresso_abas.text())
        self.w.undo_stack.undo()  # desfazer desmarca
        self.assertFalse(self.w.pagina_feita(0))
        self.w.undo_stack.redo()
        self.w.adicionar_pagina(duplicar=False)
        self.w.ir_para_pagina(0)
        self.w.adicionar_pagina(duplicar=True)  # a cópia de uma feita ainda não foi cortada
        self.assertEqual(self.w.nomes_paginas[1], "Página 1 (cópia)")

        class Maquina:
            trabalho = cx.TRABALHO_ERRO
        job = ["G1 X1"]
        self.w._job_visto = job
        self.w._aba_do_trabalho = (2, "Página 2", job)
        self.w._marcar_aba_do_trabalho(Maquina)  # parado/erro: não marca
        self.assertFalse(self.w.pagina_feita(2))
        Maquina.trabalho = cx.TRABALHO_FIM
        self.w._marcar_aba_do_trabalho(Maquina)  # terminou: marca a aba de onde saiu
        self.assertTrue(self.w.pagina_feita(2))
        self.assertIsNone(self.w._aba_do_trabalho)
        arq = os.path.join(self.tmp.name, "f.rbl")
        self.assertTrue(self.w.save_to(arq))
        w2 = MainWindow(QSettings(os.path.join(self.tmp.name, "t4.ini"), QSettings.IniFormat))
        w2.ask_save = lambda: "discard"
        w2.show_info = w2.show_error = lambda *a: None
        self.assertTrue(w2.open_path(arq))
        self.assertEqual([w2.pagina_feita(i) for i in range(len(w2.paginas))], [True, False, True, False, False])
        self.assertTrue(w2.desmarcar_todas())
        self.assertFalse(any(w2.pagina_feita(i) for i in range(len(w2.paginas))))
        w2.close()

    def test_desfazer_entre_paginas(self):
        demo = self.nomes()
        self.w.adicionar_pagina()
        self.por_quadrado("a")
        self.w.undo_stack.undo()  # tira o quadrado
        self.assertEqual(self.nomes(), [])
        self.w.undo_stack.undo()  # desfaz a página nova
        self.assertEqual((len(self.w.paginas), self.nomes()), (1, demo))
        self.w.undo_stack.redo()
        self.w.undo_stack.redo()
        self.assertEqual((len(self.w.paginas), self.w.pagina_atual, self.nomes()), (2, 1, ["a"]))

    def test_gcode_so_da_pagina_aberta_e_camadas_comuns(self):
        self.w.adicionar_pagina()
        self.por_quadrado("q", x=300)
        self.w.set_layer_field("C02", "velocidade_mm_min", 777.0)
        self.w.ir_para_pagina(0)
        self.assertEqual(self.w.layer("C02").velocidade_mm_min, 777.0)  # camadas valem para todas
        destino = os.path.join(self.tmp.name, "p1.gcode")
        self.assertTrue(self.w.export_gcode_to(destino))
        with open(destino, encoding="utf-8") as f:
            self.assertNotIn("X300.000", f.read())  # o quadrado da página 2 não vai

    def test_salvar_e_abrir(self):
        self.w.adicionar_pagina()
        self.por_quadrado("da página 2")
        self.w.ir_para_pagina(0)
        arq = os.path.join(self.tmp.name, "p.rbl")
        self.assertTrue(self.w.save_to(arq))
        with open(arq, encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual((d["versao"], d["pagina_atual"], len(d["paginas"])), (pj.VERSION, 0, 2))
        w2 = MainWindow(QSettings(os.path.join(self.tmp.name, "t2.ini"), QSettings.IniFormat))
        w2.ask_save = lambda: "discard"
        w2.show_info = w2.show_error = lambda *a: None  # sem janelas modais
        self.assertTrue(w2.open_path(arq))
        self.assertEqual((w2.abas.count(), w2.pagina_atual), (2, 0))
        w2.ir_para_pagina(1)
        self.assertEqual([s.name for s in w2.canvas.view.shapes()], ["da página 2"])
        w2.close()

    def test_projeto_invalido_e_antigo(self):
        base = {"formato": pj.FORMAT, "versao": pj.VERSION, "objetos": []}
        self.assertEqual(pj.paginas_from_dict(base), ([None], 0, ["Página 1"]))  # sem páginas = uma só
        for ruim in ({"paginas": [None, None], "pagina_atual": 0}, {"paginas": [{"objetos": []}], "pagina_atual": 0},
                     {"paginas": [None], "pagina_atual": 3}, {"paginas": [None, {"objetos": 5}], "pagina_atual": 0}):
            with self.assertRaises(pj.ProjetoInvalido, msg=ruim):
                pj.paginas_from_dict({**base, **ruim})

    def test_nomes_como_excel(self):
        self.assertTrue(self.w.renomear_pagina(0, "  Parte 1  "))
        self.w.adicionar_pagina()
        self.w.adicionar_pagina(duplicar=True)
        self.assertEqual(self.w.nomes_paginas, ["Parte 1", "Página 2", "Página 2 (cópia)"])
        self.assertEqual([self.w.abas.tabText(i) for i in range(3)], self.w.nomes_paginas)
        self.assertFalse(self.w.renomear_pagina(1, "   "))  # nome vazio recusado
        self.w.undo_stack.undo()  # desfaz a duplicação
        self.assertEqual(self.w.nomes_paginas, ["Parte 1", "Página 2"])
        self.w.excluir_pagina()
        self.assertEqual(self.w.nomes_paginas, ["Parte 1"])
        arq = os.path.join(self.tmp.name, "n.rbl")
        self.w.save_to(arq)  # uma página só, mas com nome: o nome é salvo
        w2 = MainWindow(QSettings(os.path.join(self.tmp.name, "t3.ini"), QSettings.IniFormat))
        w2.ask_save = lambda: "discard"
        w2.show_info = w2.show_error = lambda *a: None
        self.assertTrue(w2.open_path(arq))
        self.assertEqual(w2.abas.tabText(0), "Parte 1")
        w2.close()
        c = self.w.pilha_central.widget(0).layout()  # a tela de edição (a outra é a tela de corte)
        self.assertIs(c.itemAt(0).widget(), self.w.canvas)  # abas embaixo da mesa, como no Excel


if __name__ == "__main__":
    unittest.main()
