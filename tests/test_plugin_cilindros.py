"""Plugin Cilindros e copos: contas, molde em leque e botões no projeto."""
import math
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import objetos as ob  # noqa: E402
from redblack.plugins.cilindros import calc  # noqa: E402
from redblack.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class ContasTest(unittest.TestCase):
    def test_caneca_reta_com_alca(self):
        p = calc.Peca(diametro_topo=82, diametro_base=82, altura=95, inicio=10, altura_arte=70, alca_mm=40,
                      margem_mm=5)
        r = calc.calcular(p)
        self.assertAlmostEqual(r["circ"], math.pi * 82, places=6)
        self.assertAlmostEqual(r["util"], math.pi * 82 - 40 - 10, places=6)
        self.assertFalse(r["conico"])
        self.assertAlmostEqual(r["distorcao_pct"], 0, places=9)
        self.assertTrue(r["foco_ok"])

    def test_repeticoes(self):
        p = calc.Peca(diametro_topo=60, diametro_base=60, altura=120, repeticoes=2, margem_mm=4, alca_mm=0)
        r = calc.calcular(p)
        self.assertAlmostEqual(r["passo_mm"], math.pi * 60 / 2, places=6)
        self.assertAlmostEqual(r["por_arte"], math.pi * 60 / 2 - 8, places=6)
        self.assertEqual(r["passo_graus"], 180)

    def test_copo_conico_leque_bate_com_as_circunferencias(self):
        p = calc.Peca(diametro_topo=90, diametro_base=60, altura=150, inicio=20, altura_arte=80, foco_mm=1.5)
        r = calc.calcular(p)
        self.assertAlmostEqual(r["d_cima"], 86, places=6)
        self.assertAlmostEqual(r["d_baixo"], 70, places=6)
        self.assertFalse(r["foco_ok"])  # 8 mm de variação de raio
        lq = r["leque"]
        ang = math.radians(lq["angulo_graus"])
        self.assertAlmostEqual(ang * lq["R"], r["circ_cima"], places=6)  # arco externo = volta no topo da arte
        self.assertAlmostEqual(ang * lq["Rin"], r["circ_baixo"], places=6)
        self.assertAlmostEqual(lq["R"] - lq["Rin"], math.hypot(80, 8), places=6)  # geratriz da faixa
        b = calc.caminho_leque(p).boundingRect()
        self.assertEqual((round(b.left(), 6), round(b.top(), 6)), (0, 0))
        self.assertGreater(b.width(), r["circ_baixo"] * 0.9)

    def test_erros(self):
        self.assertTrue(calc.erros(calc.Peca(altura=50, inicio=20, altura_arte=40)))
        self.assertEqual(calc.erros(calc.Peca()), [])
        with self.assertRaises(ValueError):
            calc.leque(calc.Peca(diametro_topo=70, diametro_base=70))


class JanelaTest(unittest.TestCase):
    def test_botoes_no_projeto(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = MainWindow(QSettings(os.path.join(tmp, "t.ini"), QSettings.IniFormat))
            w.ask_save = lambda: "discard"
            w.show_error = w.show_info = lambda *a: None
            w.new_document()
            jan = w.plugin_cilindros["abrir"]()
            jan.d_topo.setValue(80)
            jan.alca.setValue(30)
            jan.repet.setValue(2)
            jan.ask_ligar_rotativo = lambda: False  # não confirmou: o rotativo continua desligado
            self.assertFalse(jan.aplicar_rotativo())
            self.assertFalse(w.rotativo.ativo)
            jan.ask_ligar_rotativo = lambda: True
            self.assertTrue(jan.aplicar_rotativo())
            self.assertTrue(w.rotativo.ativo)
            self.assertAlmostEqual(w.rotativo.diametro_objeto_mm, 80, places=2)
            self.assertTrue(jan.criar_area())
            nomes = [s.name for s in w.canvas.view.shapes()]
            self.assertEqual(sum(n.startswith("Área da arte") for n in nomes), 2)
            volta = next(s for s in w.canvas.view.shapes() if s.name.startswith("Volta completa 360"))
            self.assertAlmostEqual(ob.geom_rect(volta).height(), math.pi * 80, places=4)  # Y = volta (rotativo)
            self.assertAlmostEqual(ob.geom_rect(volta).width(), jan.alt_arte.value(), places=4)  # X = altura
            self.assertFalse(w.layer("C29").saida)  # referência não grava
            self.assertFalse(jan.b_leque.isEnabled())
            jan.d_base.setValue(60)
            self.assertTrue(jan.b_leque.isEnabled())
            self.assertTrue(jan.criar_leque())
            self.assertTrue(any(s.name.startswith("Molde em leque") for s in w.canvas.view.shapes()))
            jan.perfil.resize(300, 400)
            jan.perfil.grab()
            jan.close()
            w.close()


class Prévia3DTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = MainWindow(QSettings(os.path.join(self.tmp.name, "t.ini"), QSettings.IniFormat))
        self.w.ask_save = lambda: "discard"
        self.w.show_error = self.w.show_info = lambda *a: None
        self.w.new_document()
        self.jan = self.w.plugin_cilindros["abrir"]()

    def tearDown(self):
        self.jan.close()
        self.w.close()
        self.tmp.cleanup()

    def test_meio_curvo_e_arrasto(self):
        p = calc.Peca(diametro_topo=80, diametro_base=60, altura=100, diametro_meio=90)
        self.assertAlmostEqual(calc.diametro_em(p, 50), 90, places=6)
        self.assertAlmostEqual(calc.diametro_em(p, 0), 80, places=6)
        self.assertTrue(calc.curvo(p))
        # taça: vários pontos (barriga, haste, pé) pela tabela/botões e arrastando
        self.jan.d_topo.setValue(80)
        self.jan.d_base.setValue(70)
        self.jan.altura.setValue(180)
        for z, d in ((40, 86), (100, 12), (160, 12)):
            self.jan.mudar_perfil("novo", None, z, d)
        self.assertEqual(self.jan.tabela.rowCount(), 3)
        tac = self.jan.peca()
        self.assertAlmostEqual(calc.diametro_em(tac, 130), 12, places=6)  # haste
        self.assertAlmostEqual(calc.diametro_max(tac), 86, places=6)  # a curva não passa da barriga
        self.jan.mudar_perfil("mover", 0, 150, 90)  # arrastou a barriga para baixo de tudo: reordena
        self.assertEqual(self.jan.pontos, [(100, 12), (150, 90), (160, 12)])
        self.jan.tabela.item(0, 0).setText("110")  # digitou na tabela
        self.assertEqual(self.jan.pontos[0], (110, 12))
        self.jan.mudar_perfil("remover", 1)
        self.assertEqual(len(self.jan.pontos), 2)

    def test_area_360_vira_textura_da_volta_inteira(self):
        from PySide6.QtCore import QRectF
        from redblack import formas as fm
        from redblack.plugins.cilindros import arte as art
        self.jan.d_topo.setValue(80)
        self.jan.alt_arte.setValue(40)
        self.assertTrue(self.jan.criar_area())
        area = art.area_360(self.w)
        self.assertAlmostEqual(area.height(), math.pi * 80, places=3)
        # um quadrado gravado na metade de cima da área (perto do Y = 0)
        q = ob.Shape(fm.rect_path(QRectF(area.left() + 10, area.top() + 20, 20, 20)), "Logo", "C01", "#2f6bff")
        self.w._edit("t", lambda: self.w.canvas.scene.addItem(q))
        self.w.set_layer_fields("C01", {"modo": "preenchimento"}, "t")
        img, larg, alt = art.textura_360(self.w, area, True)
        self.assertAlmostEqual(larg, math.pi * 80, places=3)  # largura da textura = volta inteira
        self.assertAlmostEqual(alt, 40, places=3)
        esc = img.width() / larg
        dentro = img.pixelColor(round((larg - 30) * esc), round(20 * esc))  # u = baixo − y, v = x − esquerda
        fora = img.pixelColor(round(150 * esc), round(20 * esc))
        self.assertGreater(dentro.alpha(), 200)
        self.assertEqual(fora.alpha(), 0)
        self.jan.fonte.setCurrentIndex(0)
        self.assertTrue(self.jan.atualizar_arte())
        self.jan.vista.resize(400, 400)
        self.jan.vista.grab()

    def test_controles_novos(self):
        # base editável sem trava, meio com altura própria, cores por material e trocáveis
        self.jan.d_topo.setValue(80)
        self.jan.d_base.setValue(60)
        self.assertEqual(self.jan.peca().diametro_base, 60)
        self.jan.mudar_perfil("novo", None, 30, 90)
        p = self.jan.peca()
        self.assertEqual(p.pontos, ((30, 90),))
        self.assertAlmostEqual(calc.diametro_em(p, 30), 90, places=6)
        self.jan.material.setCurrentIndex(0)  # copo pintado: gravação cinza metálico
        self.assertEqual(self.jan.cores[1], "#b4b8be")
        self.jan.ask_cor = lambda atual, titulo: "#c0392b"
        self.jan._escolher_cor("corpo")
        self.assertEqual(self.jan.cores[0], "#c0392b")
        self.assertEqual(self.jan.vista.cor_corpo, "#c0392b")
        # arrastar para a direita gira o copo para a direita (a frente vai para +x)
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QMouseEvent
        v = self.jan.vista
        yaw0 = v.yaw
        for k, pos in ((QEvent.MouseButtonPress, QPointF(100, 100)), (QEvent.MouseMove, QPointF(140, 100)),
                       (QEvent.MouseButtonRelease, QPointF(140, 100))):
            b = Qt.LeftButton
            app.sendEvent(v, QMouseEvent(k, pos, pos, b if k != QEvent.MouseMove else Qt.NoButton, b,
                                         Qt.NoModifier))
        self.assertAlmostEqual((v.yaw - yaw0) % 360, 20, places=6)

    def test_luz_acompanha_a_vista(self):
        """Girando para ver o lado de trás, ele não fica escuro: a luz gira junto com a câmera."""
        from redblack.plugins.cilindros import vista3d as v3
        v = v3.Vista3D()
        v.resize(300, 300)
        v.definir(p=calc.Peca(diametro_topo=80, diametro_base=70, altura=120), cores=("#b9bec4", "#55585d"))

        def brilho(yaw):
            v.yaw = yaw
            img = v.grab().toImage()
            vals = [img.pixelColor(x, y).lightness() for x in range(130, 170, 5) for y in range(130, 170, 5)]
            return sum(vals) / len(vals)
        frente = brilho(0)
        self.assertGreater(frente, 90)
        for yaw in (90, 180, 270):
            self.assertAlmostEqual(brilho(yaw), frente, delta=3)

    def test_arrastar_no_3d_move_na_area_de_trabalho(self):
        from PySide6.QtCore import QEvent, QPointF, QRectF
        from PySide6.QtGui import QMouseEvent
        from redblack import formas as fm
        from redblack.plugins.cilindros import arte as art
        self.jan.d_topo.setValue(80)
        self.jan.d_base.setValue(80)
        self.assertTrue(self.jan.criar_area())
        area = art.area_360(self.w)
        q = ob.Shape(fm.rect_path(QRectF(area.left() + 5, area.top() + 100, 10, 10)), "Logo", "C01", "#2f6bff")
        self.w._edit("t", lambda: self.w.canvas.scene.addItem(q))
        self.jan.fonte.setCurrentIndex(0)
        self.assertTrue(self.jan.atualizar_arte())
        v = self.jan.vista
        v.resize(400, 400)

        def logo():
            return ob.geom_rect(next(s for s in self.w.canvas.view.shapes() if s.name == "Logo"))
        antes = logo()
        ang0, ini0 = self.jan.angulo.value(), self.jan.inicio.value()
        for k, pos in ((QEvent.MouseButtonPress, QPointF(200, 200)), (QEvent.MouseMove, QPointF(240, 200)),
                       (QEvent.MouseMove, QPointF(260, 200)), (QEvent.MouseButtonRelease, QPointF(260, 200))):
            bt = Qt.NoButton if k == QEvent.MouseMove else Qt.RightButton
            app.sendEvent(v, QMouseEvent(k, pos, pos, bt, Qt.RightButton, Qt.NoModifier))
        depois = logo()
        du = math.radians(30) * 40  # 60 px × 0,5°/px = 30° em volta, raio 40 mm
        self.assertAlmostEqual(depois.center().y() - antes.center().y(), -du, places=3)  # boca à esquerda: −Y
        self.assertAlmostEqual(depois.center().x(), antes.center().x(), places=6)
        self.assertEqual((self.jan.angulo.value(), self.jan.inicio.value()), (ang0, ini0))  # prévia não "soma"
        self.w.undo_stack.undo()  # um passo só
        self.assertAlmostEqual(logo().center().y(), antes.center().y(), places=6)
        # passou da borda: volta pelo outro lado (como no copo)
        self.jan.mover_arte_na_area(area, 0, -150)
        self.assertTrue(area.top() <= logo().center().y() <= area.bottom())
        self.assertAlmostEqual(logo().center().y(), antes.center().y() - 150 + area.height(), places=4)

    def test_desfazer_no_plugin_setas_e_faixa(self):
        from PySide6.QtCore import QEvent, QPointF, QRectF
        from PySide6.QtGui import QKeyEvent
        from redblack import formas as fm
        from redblack.plugins.cilindros import arte as art
        # Ctrl+Z do plugin desfaz medidas
        self.jan.d_topo.setValue(80)
        self.jan._registrar_hist()
        self.jan.d_topo.setValue(95)
        self.jan.desfazer()
        self.assertEqual(self.jan.d_topo.value(), 80)
        self.jan.refazer()
        self.assertEqual(self.jan.d_topo.value(), 95)
        # setas no desenho de lado e no 3D sobem/descem a faixa da arte
        ini = self.jan.inicio.value()
        app.sendEvent(self.jan.perfil, QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier))
        self.assertAlmostEqual(self.jan.inicio.value(), ini + 1, places=6)
        app.sendEvent(self.jan.vista, QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.ShiftModifier))
        self.assertAlmostEqual(self.jan.inicio.value(), ini + 11, places=6)
        app.sendEvent(self.jan.vista, QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier))
        self.assertAlmostEqual(self.jan.angulo.value(), 5, places=6)
        self.jan.mudar_perfil("faixa", None, 20.0, None)  # arrastar a faixa vermelha
        self.assertAlmostEqual(self.jan.inicio.value(), 20, places=6)
        # arte movida no copo: não sai da área em X e Ctrl+Z do plugin desfaz o movimento
        self.assertTrue(self.jan.criar_area())
        area = art.area_360(self.w)
        q = ob.Shape(fm.rect_path(QRectF(area.right() - 20, area.top() + 50, 15, 10)), "Logo", "C01", "#2f6bff")
        self.w._edit("t", lambda: self.w.canvas.scene.addItem(q))
        self.jan.mover_arte_na_area(area, 30, 0)  # empurrou para fora pela base do copo
        logo = ob.geom_rect(next(s for s in self.w.canvas.view.shapes() if s.name == "Logo"))
        self.assertAlmostEqual(logo.right(), area.right(), places=6)  # encostou na borda
        self.jan.desfazer()
        logo = ob.geom_rect(next(s for s in self.w.canvas.view.shapes() if s.name == "Logo"))
        self.assertAlmostEqual(logo.left(), area.right() - 20, places=6)

    def test_arte_acompanha_o_projeto(self):
        from PySide6.QtCore import QRectF
        from redblack import formas as fm
        from redblack.plugins.cilindros import arte as art
        self.jan.show()
        self.assertTrue(self.jan.criar_area())
        area = art.area_360(self.w)
        q = ob.Shape(fm.rect_path(QRectF(area.left() + 5, area.top() + 10, 10, 10)), "Logo", "C01", "#2f6bff")
        self.w._edit("t", lambda: self.w.canvas.scene.addItem(q))
        self.jan._projeto_mudou()
        antes = self.jan.vista.arte[0].copy()
        logo = next(s for s in self.w.canvas.view.shapes() if s.name == "Logo")
        self.w._edit("mover", lambda: ob.move_by([logo], 0, 60))  # moveu no plano
        self.assertTrue(self.jan._t_arte.isActive())  # a prévia vai se atualizar sozinha
        self.jan._t_arte.stop()
        self.jan._projeto_mudou()
        self.assertNotEqual(antes, self.jan.vista.arte[0])

    def test_parametros_salvos_por_projeto(self):
        arq = os.path.join(self.tmp.name, "copo.rbl")
        self.w.save_to(arq)
        self.jan.d_topo.setValue(77)
        self.jan.mudar_perfil("novo", None, 50, 88)
        self.jan.angulo.setValue(45)
        self.jan.material.setCurrentIndex(1)
        self.jan.salvar_estado()
        self.jan.d_topo.setValue(60)
        self.assertTrue(self.jan.carregar_estado())
        self.jan.pontos = []
        self.assertTrue(self.jan.carregar_estado())
        self.assertEqual((self.jan.d_topo.value(), self.jan.pontos, self.jan.angulo.value()), (77, [(50, 88)], 45))
        self.assertEqual(self.jan.material.currentIndex(), 1)

    def test_render_na_placa_de_video(self):
        from redblack.plugins.cilindros import render
        if not render.localizar_blender():
            self.skipTest("Blender não instalado")
        self.jan.sem_janela_render = True
        saida = self.jan.renderizar(esperar=True, resolucao=96, amostras=4)
        app.processEvents()
        self.assertTrue(os.path.isfile(saida), getattr(self.jan, "ultimo_log", ""))


if __name__ == "__main__":
    unittest.main()
