"""Tela de corte (F9): tempo decorrido/restante que se corrige pelo tempo real, botões grandes, volta à edição."""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRectF  # noqa: E402

from redblack import conexao as cx  # noqa: E402
from redblack import formas as fm  # noqa: E402
from redblack import tempo_trabalho as tt  # noqa: E402
from tests.test_painel_controle import PainelControleTest  # noqa: E402


class TempoTrabalhoTest(unittest.TestCase):
    def test_estimativa_e_previsao(self):
        cum = tt.estimar(["G21", "G0 X60 Y0", "G1 X60 Y60 F600", "G1 X0 F1200"], rapido=3600)
        self.assertEqual([round(v, 2) for v in cum], [0.0, 1.0, 7.0, 10.0])
        p = tt.Previsao([float(i) for i in range(1, 101)])  # 100 s estimados, 1 s por linha
        self.assertEqual(p.restante(10, 10.0), (90.0, 1.0))  # pouco tempo ainda: estimativa pura
        restante, fator = p.restante(40, 60.0)  # a máquina está levando 1,5× o estimado
        self.assertAlmostEqual(fator, 1.5)
        self.assertAlmostEqual(restante, 90.0)  # 60 s estimados que faltam × 1,5
        self.assertEqual(tt.fmt(3725), "1 h 02 min")
        self.assertEqual(tt.fmt(75), "1 min 15 s")

    def test_trechos_com_laser(self):
        t = tt.trechos_com_laser(["G0 X10 Y0", "G1 X20 S500 F600", "G1 X30 S0", "G1 Y5 S400", "G0 X0 Y0"])
        self.assertEqual(t, [None, ((10, 0), (20, 0)), None, ((30, 0), (30, 5)), None])  # só com laser e andando

    def test_camada_de_cada_linha(self):
        texto = ("; cabeçalho\nG21\n; Camada C02 (Furos (antes)): linha, 650 mm/min\nG1 X1\n\n"
                 "; Camada C01 (Contornos): linha\nG1 X2 ; fim\n")
        self.assertEqual(tt.camadas(texto), ["", "C02 Furos (antes)", "C01 Contornos"])
        self.assertEqual(len(tt.camadas(texto)), len(cx.Conexao.linhas_do_gcode(texto)))


class TelaCorteTest(unittest.TestCase):
    setUp, tearDown = PainelControleTest.setUp, PainelControleTest.tearDown  # só a preparação (simulador)
    ticks, conectar = PainelControleTest.ticks, PainelControleTest.conectar

    def test_abre_no_trabalho_mostra_tempo_e_volta_igual(self):
        w = self.w
        visiveis = {d.objectName() for d in w.docks if d.isVisible()}
        self.conectar()
        w.ask_liberar_controle = lambda: True
        w.btn_controle.setChecked(True)
        w.create_shape(fm.rect_path(QRectF(20, 20, 80, 60)), "rect")
        w.ask_confirmar_trabalho = lambda info, caixa: True
        self.assertTrue(w.iniciar_trabalho())
        self.assertEqual(w.pilha_central.currentIndex(), 1)  # abriu sozinha (padrão)
        self.assertTrue(all(not d.isVisible() for d in w.docks))
        self.ticks(30)
        tc = w.tela_corte
        self.assertIn("Gravando", tc.estado.text())
        self.assertNotEqual(tc.tempos["restante"].text(), "—")
        self.assertIn("falta", w.progresso_trabalho.text())
        self.assertTrue(tc.btn_parar.isEnabled())
        self.assertIn("C01", tc.camada.text())
        tc.btn_pausar.click()
        self.ticks(5)
        self.assertEqual(w.conexao.trabalho, cx.TRABALHO_PAUSADO)
        self.assertIn("RETOMAR", tc.btn_pausar.text())
        tc.btn_parar.click()
        self.ticks(5)
        self.assertIn("Parado", tc.estado.text())
        tc.btn_voltar.click()  # volta para a edição com os painéis como estavam
        self.assertEqual(w.pilha_central.currentIndex(), 0)
        self.assertEqual({d.objectName() for d in w.docks if d.isVisible()}, visiveis)
        self.assertFalse(w.act_tela_corte.isChecked())

    def test_sem_abrir_sozinha(self):
        self.w.settings.setValue("tela_corte_auto", False)
        self.conectar()
        self.w.ask_liberar_controle = lambda: True
        self.w.btn_controle.setChecked(True)
        self.w.create_shape(fm.rect_path(QRectF(20, 20, 30, 30)), "rect")
        self.w.ask_confirmar_trabalho = lambda info, caixa: True
        self.assertTrue(self.w.iniciar_trabalho())
        self.assertEqual(self.w.pilha_central.currentIndex(), 0)  # continua na edição
        self.w.act_tela_corte.trigger()  # F9
        self.assertEqual(self.w.pilha_central.currentIndex(), 1)


del PainelControleTest  # não roda os testes do painel de novo aqui

if __name__ == "__main__":
    unittest.main()
