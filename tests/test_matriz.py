"""Matriz de testes de materiais (Etapa 18)."""
import os
import re
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import gcode as gc  # noqa: E402
from redblack import materiais as mt  # noqa: E402
from redblack import matriz as mz  # noqa: E402
from redblack.simulador import SimuladorGrbl  # noqa: E402,F401  (garante que o módulo importa)
from redblack.ui.dialogo_matriz import MatrizDialog  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
M = mz.Matriz(pot_min=10, pot_max=50, colunas=5, vel_min=1000, vel_max=3000, linhas=3)


class MatrizTest(unittest.TestCase):
    def test_valores_e_celulas(self):
        self.assertEqual(M.potencias(), [10, 20, 30, 40, 50])
        self.assertEqual(M.velocidades(), [1000, 2000, 3000])
        self.assertEqual(mz.Matriz(colunas=1, pot_min=30, pot_max=30).potencias(), [30])
        snaps, camadas = mz.documento(M)
        self.assertEqual(len(snaps), 1 + 15)                                 # rótulos + 15 quadrados
        self.assertEqual(camadas[0].id, "MROT")                              # rótulos saem primeiro
        c = next(c for c in camadas if c.id == "M0204")                      # linha 3 (3000), coluna 5 (50 %)
        self.assertEqual((c.velocidade_mm_min, c.potencia_max, c.modo), (3000, 50, "preenchimento"))

    def test_gcode_cada_celula_com_seus_parametros(self):
        texto, perc = mz.gerar(M)
        info = gc.analisar(texto)
        self.assertTrue(info["dentro_da_area"] and info["fim_desligado"])
        ss = {int(v) for v in re.findall(r"\bS(\d+)", texto)}
        self.assertTrue({100, 200, 300, 400, 500} <= ss)                    # 10–50 % de S1000
        fs = {float(v) for v in re.findall(r"\bF([\d.]+)", texto)}
        self.assertTrue({1000.0, 2000.0, 3000.0} <= fs)
        self.assertIn("; Matriz de testes: 5 potencias 10-50 %", texto)
        self.assertGreater(perc.tempo_s, 0)

    def test_sem_rotulos_e_recusas(self):
        snaps, camadas = mz.documento(mz.Matriz(rotulos=False, colunas=2, linhas=2))
        self.assertEqual(len(snaps), 4)
        for ruim in (mz.Matriz(pot_min=60, pot_max=50), mz.Matriz(vel_min=5000, vel_max=1000),
                     mz.Matriz(colunas=21), mz.Matriz(x_mm=5),                # rótulos sairiam da mesa
                     mz.Matriz(celula_mm=50, colunas=20), mz.Matriz(pot_max=120), mz.Matriz(colunas=2.0)):
            self.assertTrue(mz.erros(ruim, 400, 400), ruim)
            with self.assertRaises(gc.GcodeInvalido):
                mz.gerar(ruim)

    def test_teste_de_corte_velocidade_por_passadas(self):
        m = mz.Matriz(modo="linha", colunas_param="velocidade", pot_fixa=80.0, vel_min=200.0, vel_max=600.0,
                      colunas=3, linhas_param="passadas", lin_min=1, lin_max=3, linhas=3, comando="M4")
        self.assertEqual(mz.erros(m, 400, 400), [])
        self.assertEqual(m.parametros(0, 0), (200.0, 80.0, 1, m.intervalo_mm))  # velocidade na coluna, pot. fixa
        self.assertEqual(m.parametros(2, 2), (600.0, 80.0, 3, m.intervalo_mm))
        texto, _ = mz.gerar(m)
        self.assertIn("M4 S0", texto)  # modo do laser escolhido no teste
        self.assertIn("velocidades 200-600 mm/min a 80 %", texto)
        self.assertEqual(mz.de_gcode(texto), m)  # reabre do arquivo
        ruim = mz.Matriz(colunas_param="velocidade", linhas_param="velocidade")
        self.assertTrue(any("ao mesmo tempo" in e for e in mz.erros(ruim, 400, 400)))

    def test_teste_de_precisao(self):
        texto, perc = mz.gerar_precisao(30, 30, 100, 15, 1500)
        self.assertTrue(gc.analisar(texto)["dentro_da_area"])
        xs = [float(x) for x in re.findall(r"X(-?[\d.]+)", texto)]
        self.assertTrue(any(abs(x - 30) < 0.01 for x in xs) and any(abs(x - 130) < 0.01 for x in xs))  # 100 mm
        with self.assertRaises(gc.GcodeInvalido):
            mz.gerar_precisao(30, 30, 380, 15, 1500)  # não cabe

    def test_corte_em_linha(self):
        texto, _ = mz.gerar(mz.Matriz(modo="linha", colunas=2, linhas=1, passadas=2, rotulos=False))
        self.assertEqual(texto.count("; Camada M00"), 2)


class JanelaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.win = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(("erro", m))
        self.win.show_info = lambda t, m: self.msgs.append(("info", m))

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def test_exportar_nao_mexe_no_projeto(self):
        antes = self.win.doc_state()
        p = os.path.join(self.tmp.name, "m.gcode")
        self.assertTrue(self.win.exportar_matriz(M, p))
        self.assertTrue(os.path.exists(p))
        self.assertEqual(self.win.doc_state(), antes)
        self.assertEqual(self.msgs[-1][0], "info")
        self.assertFalse(self.win.exportar_matriz(mz.Matriz(pot_min=90, pot_max=10), p + "2"))
        self.assertFalse(os.path.exists(p + "2"))

    def test_dialogo_ida_e_volta_e_faixa_do_material(self):
        mdf = next(m for m in mt.REFERENCIA_S30_PRO_MAX_20W if m.nome == "MDF" and m.operacao == "gravação")
        dlg = MatrizDialog(self.win, M, mdf)
        self.assertEqual(dlg.matriz(), M)
        self.assertTrue(dlg.btn_ok.isEnabled())
        dlg.usar_material()
        m = dlg.matriz()
        self.assertEqual((m.pot_min, m.pot_max, m.vel_min, m.vel_max), (9, 27, 1500, 4500))
        dlg.campos["pot_min"].setValue(80)
        dlg.campos["pot_max"].setValue(20)
        self.assertFalse(dlg.btn_ok.isEnabled())
        self.assertIn("potência inicial", dlg.resumo.text())


class QuadradoEscolhidoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat)
        self.win = MainWindow(self.settings)
        self.win.ask_save = lambda: "discard"
        self.msgs = []
        self.win.show_error = lambda t, m: self.msgs.append(("erro", m))
        self.win.show_info = lambda t, m: self.msgs.append(("info", m))

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def test_material_da_celula(self):
        mat = mz.material(M, 2, 4, "MDF cru", 3)                       # linha 3 = 3000, coluna 5 = 50 %
        self.assertEqual((mat.velocidade_mm_min, mat.potencia_max, mat.operacao, mat.origem, mat.air),
                         (3000, 50, "gravação", "meu", True))
        self.assertIn("50 % × 3000 mm/min", mat.nota)
        for args in ((3, 0, "x", 0), (0, 5, "x", 0), (0, 0, "  ", 0)):
            with self.assertRaises(ValueError):
                mz.material(M, *args)

    def test_parametros_no_gcode_e_ida_e_volta(self):
        self.assertEqual(mz.de_dict(mz.para_dict(M)), M)
        texto, _ = mz.gerar(M)
        self.assertEqual(mz.de_gcode(texto), M)                         # reabre a matriz pelo arquivo
        self.assertTrue(gc.analisar(texto)["dentro_da_area"])          # a linha extra é só comentário
        for ruim in ("G1 X1\n", texto.replace('"colunas": 5', '"colunas": "5"'),
                     texto.replace('"pot_max": 50,', '"pot_max": 500,')):
            with self.assertRaises(ValueError):
                mz.de_gcode(ruim)

    def test_salvar_pelo_quadrado_e_lembrar_entre_sessoes(self):
        p = os.path.join(self.tmp.name, "m.gcode")
        self.win.exportar_matriz(M, p)
        self.win.close()
        self.win = MainWindow(self.settings)                           # outro dia: matriz lembrada
        self.win.ask_save = lambda: "discard"
        self.assertEqual(self.win._ultima_matriz, M)
        self.win.ask_resultado_matriz = lambda m: (1, 3, "Couro curtido", 0, "")
        self.win._resultado_matriz_dialogo()
        meus = mt.meus(self.settings)
        self.assertEqual([(x.nome, x.potencia_max, x.velocidade_mm_min) for x in meus], [("Couro curtido", 40, 2000)])
        self.assertTrue(self.win.mat_list.item(0).text().startswith("[Meu] Couro curtido"))

    def test_sem_matriz_avisa(self):
        self.win._resultado_matriz_dialogo()
        self.assertEqual(self.msgs[-1][0], "info")
        self.assertEqual(mt.meus(self.settings), [])

    def test_dialogo_clicar_quadrado(self):
        from redblack.ui.dialogo_resultado_matriz import ResultadoMatrizDialog
        dlg = ResultadoMatrizDialog(self.win, M)
        self.assertFalse(dlg.btn_ok.isEnabled())
        dlg.grupo.button(1 * M.colunas + 2).click()                     # linha 2, coluna 3
        dlg.nome.setText("MDF")
        self.assertTrue(dlg.btn_ok.isEnabled())
        self.assertEqual(dlg.resultado()[:3], (1, 2, "MDF"))
        self.assertIn("30 % · 2000 mm/min", dlg.lbl_escolha.text())
        outra = mz.Matriz(colunas=2, linhas=2, pot_min=20, pot_max=40)
        p = os.path.join(self.tmp.name, "outra.gcode")
        with open(p, "w", encoding="utf-8") as f:
            f.write(mz.gerar(outra)[0])
        dlg.pedir_arquivo = lambda: p
        dlg._abrir_arquivo()                                            # outra matriz pelo arquivo
        self.assertEqual(dlg.m, outra)
        self.assertIsNone(dlg.escolha)
        self.assertEqual(len(dlg.grupo.buttons()), 4)
        dlg.pedir_arquivo = lambda: __file__
        dlg._abrir_arquivo()
        self.assertIn("não é uma matriz", dlg.lbl_escolha.text())



class LinhasVariamTest(unittest.TestCase):
    def test_teste_de_intervalo(self):
        m = mz.Matriz(linhas_param="intervalo", lin_min=0.05, lin_max=0.25, linhas=3, colunas=2, vel_min=2000)
        self.assertEqual(m.valores_linhas(), [0.05, 0.15, 0.25])
        self.assertEqual(m.parametros(2, 1), (2000, 50, 1, 0.25))
        snaps, camadas = mz.documento(m)
        self.assertEqual({c.intervalo_mm for c in camadas if c.id != "MROT"}, {0.05, 0.15, 0.25})
        self.assertEqual({c.velocidade_mm_min for c in camadas if c.id != "MROT"}, {2000})
        texto, _ = mz.gerar(m)
        self.assertEqual(mz.de_gcode(texto), m)
        mat = mz.material(m, 0, 0, "MDF", 3)
        self.assertEqual((mat.intervalo_mm, mat.velocidade_mm_min), (0.05, 2000))

    def test_passadas_e_validacao(self):
        m = mz.Matriz(linhas_param="passadas", lin_min=1, lin_max=4, linhas=4, modo="linha")
        self.assertEqual(m.valores_linhas(), [1, 2, 3, 4])
        self.assertEqual(mz.material(m, 3, 0, "x", 3).passadas, 4)
        self.assertTrue(mz.erros(mz.Matriz(linhas_param="intervalo", lin_min=0.001, lin_max=0.1), 400, 400))
        self.assertTrue(mz.erros(mz.Matriz(linhas_param="xyz"), 400, 400))

    def test_matriz_antiga_sem_campos_novos(self):
        d = mz.para_dict(M)
        for k in ("linhas_param", "lin_min", "lin_max"):
            del d[k]
        self.assertEqual(mz.de_dict(d).linhas_param, "velocidade")

    def test_dialogos(self):
        from redblack.ui.dialogo_resultado_matriz import ResultadoMatrizDialog
        m = mz.Matriz(linhas_param="intervalo", lin_min=0.1, lin_max=0.3, linhas=3, colunas=2)
        dlg = MatrizDialog(None, m)
        self.assertEqual(dlg.matriz(), m)
        self.assertFalse(dlg.campos["vel_max"].isEnabled())
        r = ResultadoMatrizDialog(None, m)
        r.grupo.button(5).click()                                           # linha 3, coluna 2
        self.assertIn("intervalo 0,3 mm", r.lbl_escolha.text())


if __name__ == "__main__":
    unittest.main()
