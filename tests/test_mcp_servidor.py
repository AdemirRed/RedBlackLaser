"""Servidor MCP: protocolo (initialize, tools/list, tools/call) e as ferramentas sobre um projeto real."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from PySide6.QtWidgets import QApplication  # noqa: E402

from redblack import mcp_servidor as ms  # noqa: E402
from redblack import projeto as pj  # noqa: E402

app = QApplication.instance() or QApplication([])


def chamar(_ferramenta, **args):
    r = ms.tratar({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": _ferramenta, "arguments": args}})
    res = r["result"]
    texto = res["content"][0]["text"]
    return res["isError"], (texto if res["isError"] else json.loads(texto))


class McpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "peca.rbl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_protocolo(self):
        r = ms.tratar({"jsonrpc": "2.0", "id": 7, "method": "initialize",
                       "params": {"protocolVersion": "2025-03-26", "capabilities": {}}})
        self.assertEqual(r["id"], 7)
        self.assertEqual(r["result"]["protocolVersion"], "2025-03-26")
        self.assertIn("tools", r["result"]["capabilities"])
        self.assertIsNone(ms.tratar({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        nomes = [t["name"] for t in ms.tratar({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]]
        self.assertIn("gerar_gcode", nomes)
        self.assertIn("error", ms.tratar({"jsonrpc": "2.0", "id": 3, "method": "nada"}))

    def test_fluxo_completo(self):
        erro, r = chamar("criar_projeto", arquivo=self.arq, paginas=["Parte 1", "Parte 2"])
        self.assertFalse(erro, r)
        self.assertTrue(chamar("criar_projeto", arquivo=self.arq)[0])  # não sobrescreve sem pedir
        erro, r = chamar("adicionar_forma", arquivo=self.arq, tipo="retangulo", x=10, y=10, largura=100, altura=50,
                         raio_canto=5, nome="Placa")
        self.assertFalse(erro, r)
        self.assertEqual((r["largura"], r["altura"]), (100, 50))
        erro, r = chamar("adicionar_forma", arquivo=self.arq, tipo="circulo", x=60, y=35, diametro=20, camada="C02",
                         nome="Furo")
        self.assertFalse(erro, r)
        erro, r = chamar("adicionar_forma", arquivo=self.arq, tipo="caminho_svg", d="M 0 0 C 10 -10 20 10 30 0",
                         x=20, y=100, pagina="Parte 2", nome="Onda")
        self.assertFalse(erro, r)
        erro, r = chamar("adicionar_forma", arquivo=self.arq, tipo="texto", texto="RB", x=20, y=200, altura_texto=8,
                         pagina=2)
        self.assertFalse(erro, r)
        erro, r = chamar("configurar_camada", arquivo=self.arq, camada="C02",
                         campos={"nome": "Furos", "velocidade_mm_min": 400, "potencia_max": 90, "passadas": 2})
        self.assertFalse(erro, r)
        self.assertTrue(chamar("configurar_camada", arquivo=self.arq, camada="C02", campos={"potencia_max": 500})[0])
        erro, info = chamar("projeto_info", arquivo=self.arq)
        self.assertEqual([p["objetos"] for p in info["paginas"]], [2, 2])
        erro, lst = chamar("listar_objetos", arquivo=self.arq, pagina=1)
        self.assertEqual([o["nome"] for o in lst["objetos"]], ["Placa", "Furo"])
        gcode = os.path.join(self.tmp.name, "p1.gcode")
        erro, r = chamar("gerar_gcode", arquivo=self.arq, destino=gcode, pagina=1)
        self.assertFalse(erro, r)
        with open(gcode, encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("F400", txt)  # velocidade da camada C02 configurada
        self.assertTrue(chamar("gerar_gcode", arquivo=self.arq, destino=gcode)[0])  # não sobrescreve sem pedir
        erro, r = chamar("gerenciar_pagina", arquivo=self.arq, acao="renomear", pagina=2, nome="Tampa")
        self.assertEqual(r["paginas"], ["Parte 1", "Tampa"])
        erro, r = chamar("gerenciar_pagina", arquivo=self.arq, acao="duplicar", pagina="Tampa")
        self.assertEqual(r["paginas"], ["Parte 1", "Tampa", "Tampa (cópia)"])
        erro, r = chamar("gerenciar_pagina", arquivo=self.arq, acao="excluir", pagina=1)
        self.assertEqual(r["paginas"], ["Tampa", "Tampa (cópia)"])
        erro, r = chamar("remover_objetos", arquivo=self.arq, pagina=1, nomes=["Onda"])
        self.assertEqual((r["removidos"], r["restam"]), (1, 1))
        # o projeto abre no programa normalmente
        _, layers, *_resto, (pags, atual, nomes) = pj.load_full(self.arq)
        self.assertEqual(nomes, ["Tampa", "Tampa (cópia)"])
        self.assertIn("C02", [c.id for c in layers])

    def test_erros_explicados(self):
        erro, msg = chamar("projeto_info", arquivo=os.path.join(self.tmp.name, "nao.rbl"))
        self.assertTrue(erro)
        self.assertIn("não encontrado", msg)
        chamar("criar_projeto", arquivo=self.arq)
        self.assertTrue(chamar("adicionar_forma", arquivo=self.arq, tipo="circulo")[0])  # sem diâmetro
        self.assertTrue(chamar("adicionar_forma", arquivo=self.arq, tipo="retangulo", x=0, y=0, largura=5,
                               altura=5, camada="X9")[0])
        self.assertTrue(chamar("listar_objetos", arquivo=self.arq, pagina=9)[0])
        erro, msg = chamar("projeto_info")  # argumento faltando
        self.assertTrue(erro)

    def test_por_stdio_como_o_claude_usa(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "criar_projeto", "arguments": {"arquivo": self.arq, "paginas": ["Ção"]}}}]
        entrada = "\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n"
        p = subprocess.run([sys.executable, "-m", "redblack.mcp_servidor"], input=entrada.encode("utf-8"),
                           capture_output=True, cwd=RAIZ, timeout=60)
        linhas = [json.loads(x) for x in p.stdout.decode("utf-8").splitlines() if x.strip()]
        self.assertEqual([x["id"] for x in linhas], [1, 2, 3])  # só respostas JSON no stdout
        self.assertFalse(linhas[2]["result"]["isError"])
        self.assertIn("Ção", linhas[2]["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
