"""Texto variável e arquivos recentes — pedidos do usuário."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import formas as fm  # noqa: E402
from redblack import gcode as gc  # noqa: E402
from redblack import objetos as ob  # noqa: E402
from redblack import projeto as pj  # noqa: E402
from redblack import texto as tx  # noqa: E402
from redblack import variaveis as vr  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
AGORA = datetime(2026, 11, 8, 14, 5)
CSV_EXCEL = "Nome;Modelo\nJoão da Silva;Faca 8\"\nMaria Conceição;Faca 6\"\nJosé;Canivete\n".encode("cp1252")


class MarcadoresTest(unittest.TestCase):
    def test_renderizar(self):
        d = vr.ler_csv(CSV_EXCEL)
        ctx = vr.contexto(vr.DadosVariaveis(d.colunas, d.linhas, linha_atual=1, contador=7), AGORA)
        self.assertEqual(vr.renderizar("{Nome} - {n:3} - {data} {hora} #{linha}", ctx),
                         ("Maria Conceição - 007 - 08/11/2026 14:05 #2", []))
        self.assertEqual(vr.renderizar("{nome}/{MODELO}", ctx)[0], "Maria Conceição/Faca 6\"")  # sem diferenciar maiúsculas
        self.assertEqual(vr.renderizar("{{literal}} {n}", ctx)[0], "{literal} 7")
        self.assertEqual(vr.renderizar("{Apelido}", ctx), ("{?Apelido}", ["Apelido"]))
        self.assertEqual(vr.renderizar("{n:4}", vr.contexto(vr.DadosVariaveis(contador=42), AGORA))[0], "0042")
        self.assertTrue(vr.tem_marcadores("Olá {Nome}"))
        self.assertFalse(vr.tem_marcadores("sem nada {{ }}"))

    def test_csv_formatos_e_limites(self):
        d = vr.ler_csv(CSV_EXCEL, "nomes.csv")
        self.assertEqual(d.colunas, ("Nome", "Modelo"))
        self.assertEqual(d.linhas[0], ("João da Silva", "Faca 8\""))             # acentos do Excel (cp1252)
        self.assertEqual(vr.ler_csv("nome,qtd\nAna,2\n".encode()).linhas, (("Ana", "2"),))
        self.assertEqual(vr.ler_csv("\ufeffa\tb\n1\t2\n".encode()).colunas, ("a", "b"))  # BOM + tabulação
        self.assertEqual(vr.ler_csv("x;;\n1\n".encode()).linhas, (("1", "", ""),))       # colunas faltando
        self.assertEqual(vr.ler_csv("x;;\n1\n".encode()).colunas[1], "coluna2")
        for ruim in (b"", b"so cabecalho\n", b"a\n" + b"x\n" * (vr.MAX_LINHAS + 1)):
            with self.assertRaises(vr.CsvInvalido):
                vr.ler_csv(ruim)

    def test_avancar_e_validar(self):
        d = vr.ler_csv(CSV_EXCEL)
        d = vr.DadosVariaveis(d.colunas, d.linhas, contador=1, incremento=5)
        d2 = d.avancar().avancar().avancar()
        self.assertEqual((d2.linha_atual, d2.contador), (2, 16))                 # para na última linha
        for ruim in ({"colunas": ["a"], "linhas": [["1", "2"]], "linha_atual": 0, "contador": 1, "incremento": 1},
                     {"colunas": ["a"], "linhas": [["1"]], "linha_atual": 5, "contador": 1, "incremento": 1},
                     {"colunas": ["a"], "linhas": [["1"]], "linha_atual": 0, "contador": "1", "incremento": 1},
                     "x"):
            with self.assertRaises(ValueError):
                vr.validar(ruim)


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
        self.win.new_document()
        self.csv = os.path.join(self.tmp.name, "nomes.csv")
        with open(self.csv, "wb") as f:
            f.write(CSV_EXCEL)

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def texto(self):
        return next(s for s in self.view.shapes() if isinstance(s, ob.TextShape))

    def esperado(self, texto):
        return tx.build_path(tx.TextoParams(texto, "Arial", 10))

    def criar_variavel(self, modelo="{Nome} {n:3}"):
        self.win.create_text(tx.TextoParams(modelo, "Arial", 10, variavel=True), QPointF(50, 50))

    def test_texto_acompanha_linha_e_contador(self):
        self.assertTrue(self.win.carregar_csv(self.csv))
        self.criar_variavel()
        t = self.texto()
        self.assertEqual(t.params.texto, "{Nome} {n:3}")                         # o modelo fica guardado
        self.assertEqual(t.path(), self.esperado("João da Silva 001"))           # o desenho mostra o valor
        self.win.set_vars(self.win.vars.na_linha(2), "linha 3")
        self.assertEqual(self.texto().path(), self.esperado("José 001"))
        self.win.vars_panel.avancarPedido.emit()                                 # já está na última linha
        self.assertEqual(self.texto().path(), self.esperado("José 002"))
        self.win.undo_stack.undo()
        self.assertEqual(self.texto().path(), self.esperado("José 001"))
        self.assertEqual(self.win.vars.linha_atual, 2)
        self.assertEqual(self.win.vars_panel.lbl_linha.text(), "Linha 3 de 3")

    def test_texto_fixo_com_chaves_nao_muda(self):
        self.win.carregar_csv(self.csv)
        self.win.create_text(tx.TextoParams("{Nome}", "Arial", 10), QPointF(50, 50))
        self.assertEqual(self.texto().path(), self.esperado("{Nome}"))

    def test_marcador_desconhecido_aparece_e_e_avisado(self):
        self.criar_variavel("{Apelido}")
        self.assertEqual(self.texto().path(), self.esperado("{?Apelido}"))
        self.assertFalse(self.win.vars_panel.lbl_aviso.isHidden())
        self.assertIn("{Apelido}", self.win.vars_panel.lbl_aviso.text())

    def test_texto_variavel_dentro_de_grupo(self):
        self.win.carregar_csv(self.csv)
        self.criar_variavel("{Nome}")
        self.win.create_shape(fm.rect_path(QRectF(40, 30, 120, 40)), "rect")
        self.win.select_all()
        self.win.group_selected()
        self.win.set_vars(self.win.vars.na_linha(1), "linha 2")
        g = self.view.shapes()[0]
        filho = next(c for c in g.extra.children if isinstance(c[5], tx.TextoParams))
        self.assertEqual(filho[0], self.esperado("Maria Conceição"))

    def test_projeto_guarda_planilha_e_linha(self):
        self.win.carregar_csv(self.csv)
        self.criar_variavel()
        self.win.set_vars(self.win.vars.na_linha(1), "linha 2")
        p = os.path.join(self.tmp.name, "lote.rbl")
        self.assertTrue(self.win.save_to(p))
        os.remove(self.csv)                                                       # o original some
        self.win.new_document()
        self.assertTrue(self.win.open_path(p))
        self.assertEqual(self.win.vars.linha_atual, 1)
        self.assertEqual(len(self.win.vars.linhas), 3)
        self.assertEqual(self.texto().path(), self.esperado("Maria Conceição 001"))
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual(d["variaveis"]["linhas"][0][0], "João da Silva")
        d["variaveis"]["linha_atual"] = 9
        with self.assertRaises(pj.ProjetoInvalido):
            pj.variaveis_from_dict(d)

    def test_lote_um_gcode_por_linha_sem_sobrescrever(self):
        self.win.carregar_csv(self.csv)
        self.criar_variavel("{Nome}")
        antes = self.win.doc_state()
        pasta = os.path.join(self.tmp.name, "lote")
        os.makedirs(pasta)
        feitos = self.win.exportar_lote(pasta, agora=AGORA)
        self.assertEqual([os.path.basename(f) for f in feitos],
                         ["lote_001_João_da_Silva.gcode", "lote_002_Maria_Conceição.gcode", "lote_003_José.gcode"])
        textos = [open(f, encoding="utf-8").read() for f in feitos]
        self.assertEqual(len(set(textos)), 3)                                      # cada peça diferente
        self.assertTrue(all(gc.analisar(t)["dentro_da_area"] for t in textos))
        self.assertEqual(self.win.doc_state()[0], antes[0])                         # documento intacto
        with self.assertRaises(gc.GcodeInvalido):
            self.win.exportar_lote(pasta, agora=AGORA)                               # não sobrescreve

    def test_lote_sem_planilha_usa_contador(self):
        self.criar_variavel("Nº {n:3}")
        self.win.set_vars(self.win.vars.__class__(contador=10, incremento=2), "contador")
        pasta = os.path.join(self.tmp.name, "serie")
        os.makedirs(pasta)
        feitos = self.win.exportar_lote(pasta, quantidade=3)
        self.assertEqual([os.path.basename(f) for f in feitos],
                         ["lote_001_10.gcode", "lote_002_12.gcode", "lote_003_14.gcode"])

    def test_recentes(self):
        caminhos = []
        for i in range(10):
            p = os.path.join(self.tmp.name, f"p{i}.rbl")
            self.win.save_to(p)
            caminhos.append(os.path.abspath(p))
        self.assertEqual(self.win.recentes(), caminhos[::-1][:8])                 # mais recente primeiro, máx. 8
        self.win.open_path(caminhos[3])
        self.assertEqual(self.win.recentes()[0], caminhos[3])                      # reabrir sobe para o topo
        self.assertEqual(len(set(self.win.recentes())), 8)                         # sem repetidos
        self.win._montar_recentes()
        textos = [a.text() for a in self.win.recent_menu.actions() if a.text()]
        self.assertTrue(textos[0].startswith("&1 p3.rbl"))
        self.assertEqual(textos[-1], "Limpar lista")
        os.remove(caminhos[9])
        self.assertFalse(self.win.abrir_recente(caminhos[9]))
        self.assertNotIn(caminhos[9], self.win.recentes())
        self.assertEqual(self.msgs[-1][0], "erro")
        self.assertTrue(self.win.abrir_recente(caminhos[8]))
        self.assertEqual(self.win.file_path, caminhos[8])
        self.win._limpar_recentes()
        self.assertEqual(self.win.recentes(), [])

    def test_recentes_persistem_entre_janelas(self):
        p = os.path.join(self.tmp.name, "x.rbl")
        self.win.save_to(p)
        w2 = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        w2.ask_save = lambda: "discard"
        self.assertEqual(w2.recentes(), [os.path.abspath(p)])
        w2.close()


if __name__ == "__main__":
    unittest.main()
