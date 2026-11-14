"""Plugin Plano de corte (Qt): encaixe, janela própria, CSV, lista salva e envio ao RedBlack (abas)."""
import os
import random
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import objetos as ob  # noqa: E402
from redblack.plugins.plano_corte import plano as pl  # noqa: E402
from redblack.plugins.plano_corte.janela import JanelaPlanoCorte  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def conferir(t, chapas, L, A, esp, mg):
    for ch in chapas:
        for p in ch.pecas:
            t.assertTrue(p.x >= mg - 1e-6 and p.y >= mg - 1e-6)
            t.assertTrue(p.x + p.larg <= L - mg + 1e-6 and p.y + p.alt <= A - mg + 1e-6)
        for i, a in enumerate(ch.pecas):
            for b in ch.pecas[i + 1:]:
                vao = max(b.x - (a.x + a.larg), a.x - (b.x + b.larg), b.y - (a.y + a.alt), a.y - (b.y + b.alt))
                t.assertGreaterEqual(vao, esp - 1e-6)


class EncaixeTest(unittest.TestCase):
    def test_grade_exata(self):
        chapas, fora = pl.planejar([pl.Peca(12, 98, 63, 1, girar=False)], 398, 195, espaco=2, margem=0)
        self.assertEqual((len(chapas), len(chapas[0].pecas), fora), (1, 12, []))
        conferir(self, chapas, 398, 195, 2, 0)

    def test_varias_chapas_e_girar(self):
        chapas, _ = pl.planejar([pl.Peca(7, 100, 100, 1)], 210, 210, 0, 0)
        self.assertEqual((len(chapas), sum(len(c.pecas) for c in chapas)), (2, 7))
        chapas, _ = pl.planejar([pl.Peca(1, 150, 40, 1)], 50, 200, 0, 0)
        self.assertTrue(chapas[0].pecas[0].girada)
        self.assertEqual(chapas[0].pecas[0].larg, 40)
        _, fora = pl.planejar([pl.Peca(1, 150, 40, 1, girar=False)], 50, 200, 0, 0)
        self.assertEqual(len(fora), 1)

    def test_aleatorio(self):
        rnd = random.Random(7)
        for t in range(30):
            pecas = [pl.Peca(rnd.randint(1, 4), rnd.uniform(10, 160), rnd.uniform(10, 160), 1, girar=rnd.random() < .7)
                     for _ in range(rnd.randint(1, 8))]
            esp, mg = (0, 2, 4)[t % 3], (0, 5)[t % 2]
            chapas, fora = pl.planejar(pecas, 600, 400, esp, mg)
            conferir(self, chapas, 600, 400, esp, mg)
            self.assertEqual(sum(len(c.pecas) for c in chapas) + len(fora), sum(p.qtd for p in pecas))

    def test_por_material(self):
        mats = [pl.Material(1, "A", 3, 300, 300), pl.Material(2, "B", 6, 200, 200)]
        res = pl.planejar_tudo([pl.Peca(2, 100, 100, 1), pl.Peca(1, 150, 150, 2), pl.Peca(1, 10, 10, 9)], mats)
        self.assertEqual([(m.nome if m else None, len(f)) for m, _c, f in res], [("A", 0), ("B", 0), (None, 1)])


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.enviado = []
        self.arq = os.path.join(self.tmp.name, "lista.json")
        self.j = JanelaPlanoCorte(lambda ch, cam: (self.enviado.append((ch, cam)), len(ch))[1], self.arq)

    def tearDown(self):
        self.j.close()
        self.tmp.cleanup()

    def test_editar_calcular_enviar(self):
        self.j.adicionar_peca()
        t = self.j.tab
        t.item(0, 0).setText("3")
        t.item(0, 1).setText("150")
        t.item(0, 2).setText("66,5")  # vírgula aceita
        t.item(0, 4).setText("Parede")
        self.assertEqual((self.j.pecas[0].qtd, self.j.pecas[0].alt, self.j.pecas[0].desc), (3, 66.5, "Parede"))
        t.item(0, 5).setCheckState(Qt.Unchecked)
        self.assertFalse(self.j.pecas[0].girar)
        self.j.calcular()
        self.assertEqual(self.j.abas.currentIndex(), 2)
        self.assertTrue(self.j.bt_enviar.isEnabled())
        self.j.vista.grab()  # desenha sem erro
        self.assertEqual(self.j.enviar(), 1)
        chapas, camada = self.enviado[0]
        self.assertEqual((camada, len(chapas[0]["pecas"])), ("C01", 3))
        self.assertIn("Parede 150×66,5", chapas[0]["pecas"][0]["nome"])

    def test_peca_maior_que_a_chapa(self):
        self.j.adicionar_peca()
        self.j.tab.item(0, 1).setText("900")
        self.assertTrue(self.j._grande(self.j.pecas[0]))
        self.j.calcular()
        self.assertIn("não couberam", self.j.lb_plano.text())

    def test_csv_ida_e_volta_e_lista_salva(self):
        self.j.adicionar_peca()
        self.j.tab.item(0, 4).setText("Tampa")
        csv_ = os.path.join(self.tmp.name, "l.csv")
        self.assertTrue(self.j.exportar_csv(csv_))
        with open(csv_, "a", encoding="utf-8") as f:
            f.write("2;300;200;Compensado 4 mm;Fundo;nao\n")
        self.j.nova_lista(confirmar=False)
        self.assertEqual(self.j.importar_csv(csv_), 2)
        self.assertEqual([p.desc for p in self.j.pecas], ["Tampa", "Fundo"])
        self.assertIn("Compensado 4 mm", [m.nome for m in self.j.materiais])
        self.assertFalse(self.j.pecas[1].girar)
        self.j.salvar()
        outra = JanelaPlanoCorte(lambda *a: 0, self.arq)
        self.assertEqual([p.desc for p in outra.pecas], ["Tampa", "Fundo"])
        outra.close()


class EnvioAoRedBlackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def test_menu_abre_janela_separada(self):
        textos = [a.text() for a in self.w.menu_plugins.actions()]
        self.assertTrue(any("Plano de corte" in t for t in textos), textos)
        j = self.w.plugin_plano_corte["abrir"]()
        self.assertTrue(j.isWindow() and j.isVisible())
        self.assertIsNot(j, self.w.centralWidget())
        self.assertIs(self.w.plugin_plano_corte["abrir"](), j)  # reaproveita a mesma janela
        j.close()

    def test_cria_uma_aba_por_chapa(self):
        from redblack.plugins.plano_corte import aplicar_plano
        chapas = [{"nome": "MDF 3 mm — chapa 1", "largura": 600, "altura": 400,
                   "pecas": [{"x": 5, "y": 5, "largura": 150, "altura": 66, "nome": "Parede 150×66"}]},
                  {"nome": "MDF 3 mm — chapa 2", "largura": 600, "altura": 400,
                   "pecas": [{"x": 5, "y": 5, "largura": 300, "altura": 200, "nome": "Fundo"}]}]
        antes = len(self.w.paginas)
        self.assertEqual(aplicar_plano(self.w, chapas, "C01"), 2)
        self.assertEqual(self.w.nomes_paginas[-2:], ["MDF 3 mm — chapa 1", "MDF 3 mm — chapa 2"])
        self.w.ir_para_pagina(antes)
        parede = next(s for s in self.w.canvas.view.shapes() if s.name == "Parede 150×66")
        r = ob.geom_rect(parede)
        self.assertEqual((r.x(), r.y(), r.width(), r.height()), (5, 5, 150, 66))
        self.assertFalse(self.w.layer("C29").saida)  # borda da chapa não vai para o laser
        with self.assertRaises(ValueError):
            aplicar_plano(self.w, chapas, "C29")


if __name__ == "__main__":
    unittest.main()
