"""Executa um arquivo G-code no simulador GRBL e imprime um relatório. NÃO usa máquina.

Uso: python tools/simular.py arquivo.gcode [--limites]
  --limites  liga os limites por software do simulador ($20=1, área 400 × 400 mm)

`transmitir` é um transmissor de TESTE (contagem de caracteres, como documentado para o GRBL);
o envio de verdade, com pausa/cancelamento e confirmações, é da Etapa 15.
"""
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redblack.simulador import RX_BYTES, SimuladorGrbl  # noqa: E402
from redblack.transporte import TransporteSimulado  # noqa: E402


def linhas_de_codigo(texto: str) -> list:
    """Remove comentários e linhas vazias (economiza o buffer de 128 bytes)."""
    out = []
    for raw in texto.splitlines():
        code = raw.split(";", 1)[0].strip()
        if code:
            out.append(code)
    return out


def transmitir(transporte, linhas, passo_s=0.01, limite_s=24 * 3600):
    """Envia respeitando a contagem de caracteres: soma dos bytes sem resposta ≤ 128.

    Para no primeiro ALARM (não continua o trabalho). Devolve um relatório.
    """
    pendentes = deque()
    i, oks, erros, alarmes, outras = 0, 0, [], [], []
    enviadas = []
    t = 0.0
    while (i < len(linhas) or pendentes) and t < limite_s:
        while i < len(linhas) and sum(pendentes) + len(linhas[i]) + 1 <= RX_BYTES:
            data = (linhas[i] + "\n").encode("ascii")
            transporte.escrever(data)
            pendentes.append(len(data))
            enviadas.append(i)
            i += 1
        transporte.esperar(passo_s)
        t += passo_s
        for ln in transporte.ler_linhas():
            if ln == "ok" or ln.startswith("error:"):
                n = enviadas.pop(0)
                pendentes.popleft()
                if ln == "ok":
                    oks += 1
                else:
                    erros.append((n + 1, linhas[n], ln))
            elif ln.startswith("ALARM:"):
                # No simulador, o alarme causado por uma linha substitui o "ok" dela
                # (comportamento exato do firmware real: confirmar na Etapa 13).
                n = enviadas.pop(0) if enviadas else None
                if pendentes:
                    pendentes.popleft()
                alarmes.append(ln if n is None else f"{ln} (linha {n + 1}: {linhas[n]})")
                break  # nada mais é atribuído depois de um alarme
            else:
                outras.append(ln)
        if alarmes:
            break
    # deixa terminar o que está no planejador (sem enviar mais nada)
    while transporte.sim.planner and not alarmes and t < limite_s:
        transporte.esperar(passo_s)
        t += passo_s
    return {"enviadas": i, "oks": oks, "erros": erros, "alarmes": alarmes, "mensagens": outras}


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        linhas = linhas_de_codigo(f.read())
    sim = SimuladorGrbl({20: 1} if "--limites" in argv else None)
    tr = TransporteSimulado(sim)
    tr.abrir()
    tr.ler_linhas()  # mensagem de boas-vindas
    rel = transmitir(tr, linhas)
    print(f"Linhas de código: {len(linhas)} | enviadas: {rel['enviadas']} | ok: {rel['oks']}")
    print(f"Erros: {len(rel['erros'])}")
    for n, ln, e in rel["erros"][:20]:
        print(f"  linha {n}: {e}  <- {ln}")
    print(f"Alarmes: {rel['alarmes'] or 'nenhum'}")
    print(f"Estado final: {sim.estado} | posição: X{sim.pos[0]:.3f} Y{sim.pos[1]:.3f}")
    print(f"Tempo simulado: {sim.tempo:.1f} s (sem aceleração)")
    print(f"Com laser: {sim.comprimento_com_laser():.1f} mm | segmentos: {len(sim.trilha)}")
    print(f"Bytes perdidos por estouro do buffer: {sim.estouros}")
    print(f"Laser ligado PARADO (M3): {sim.emissao_parada_s:.3f} s")
    return 0 if not rel["erros"] and not rel["alarmes"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
