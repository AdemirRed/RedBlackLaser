"""Avisos sonoros da máquina: início, pausa, parada, fim e erro. Tons gerados pelo programa (WAV curto numa pasta
temporária) e tocados sem travar a tela (winsound, Windows). Fora do Windows: o bipe do sistema."""
import math
import os
import struct
import tempfile
import wave

TAXA = 22050
# evento: [(frequência Hz, duração s), ...] — 0 Hz = silêncio
TONS = {
    "inicio": [(660, 0.10), (0, 0.04), (880, 0.14)],                       # sobe: começou
    "pausa": [(700, 0.18)],                                                # um toque: pausado
    "parado": [(520, 0.16), (0, 0.04), (390, 0.22)],                       # desce: parado pelo usuário
    "fim": [(660, 0.10), (0, 0.03), (880, 0.10), (0, 0.03), (1175, 0.22)],  # três subindo: terminou
    "erro": [(300, 0.20), (0, 0.06), (300, 0.20), (0, 0.06), (300, 0.30)],  # grave repetido: erro/alarme
}


def _gerar(nome, notas):
    pasta = os.path.join(tempfile.gettempdir(), "redblack_sons")
    os.makedirs(pasta, exist_ok=True)
    arq = os.path.join(pasta, f"{nome}.wav")
    if os.path.isfile(arq):
        return arq
    amostras = bytearray()
    for freq, dur in notas:
        n = int(TAXA * dur)
        for i in range(n):
            env = min(1.0, i / (TAXA * 0.01), (n - i) / (TAXA * 0.015))  # sem estalo no começo/fim
            v = 0.45 * env * math.sin(2 * math.pi * freq * i / TAXA) if freq else 0.0
            amostras += struct.pack("<h", int(v * 32767))
    with wave.open(arq, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(bytes(amostras))
    return arq


def arquivo(evento):
    return _gerar(evento, TONS[evento])


def tocar(evento):
    """Toca o aviso sem esperar (não trava a tela). Nunca levanta erro: som é só um aviso."""
    if evento not in TONS:
        return False
    try:
        import winsound
        winsound.PlaySound(arquivo(evento), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return True
    except Exception:  # sem winsound (outro sistema) ou sem som: bipe simples
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.beep()
        except Exception:
            pass
        return False
