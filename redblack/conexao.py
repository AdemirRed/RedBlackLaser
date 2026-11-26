"""Conexão com o controlador (GRBL).

Por padrão, SOMENTE LEITURA: só consultas que não movem nem ligam o laser ("?", $I, $$, $G).
O CONTROLE (Etapa 14/15) só existe depois de `habilitar_controle(True)` — a interface pede confirmação ao usuário:
  - mover o cabeçote com $J= (jog: nunca liga o laser; cancelável com 0x85), ir para um ponto, enquadrar;
  - desbloquear alarme ($X), homing ($H, se a máquina tiver), definir/zerar a origem (G10 L20/L2 P1);
  - enviar um trabalho: streaming por contagem de caracteres (buffer de 127 bytes do GRBL); qualquer "error:" ou
    alarme durante o trabalho PAUSA ("!") e para de enviar;
  - pausar ("!"), retomar ("~").
PARAR (reset 0x18) é sempre permitido, mesmo sem o controle: para tudo e apaga o laser na hora.

Fluxo: abrir porta → aguardar boas-vindas (placas que reiniciam ao abrir) ou responder a "?"
(placas que não reiniciam) → $I e $$ (uma consulta por vez, esperando "ok") → status periódico.
Não desbloqueia alarme, não faz homing e nunca retoma nada após reconexão.
Avança por `tick(dt)`; a interface chama periodicamente, os testes chamam diretamente.
"""
from . import grbl
from .transporte import TransporteErro

import re
import threading
from collections import deque

PERMITIDOS = ("$I", "$$", "$G")
RX_BUFFER = 127   # bytes do buffer serial do GRBL (128 − 1 de folga)
_CONTROLE = re.compile(r"^(\$J=G9[01] G21( X-?\d+(\.\d+)?)?( Y-?\d+(\.\d+)?)? F\d+(\.\d+)?|\$X|\$H|"
                       r"G10 L2(0)? P1 X-?\d+(\.\d+)? Y-?\d+(\.\d+)?|M8|M9|\$22=[01]|\$20=[01]|"
                       r"M3 S\d+(\.\d+)?|M5|G1 F\d+(\.\d+)?|\$1=\d+)$")
MIRA_POT_MAX = 2.0  # % — mira contínua (laser parado ligado): nunca passa disso
TIMEOUT_HOMING_S = 120.0  # o "ok" do $H só vem quando o cabeçote chega nos fins de curso
POT_MAX_ENQUADRAR = 5.0  # % — enquadrar com laser fraco nunca passa disso
TRABALHO_PARADO, TRABALHO_RODANDO, TRABALHO_PAUSADO, TRABALHO_FIM, TRABALHO_ERRO = (
    "Parado", "Rodando", "Pausado", "Concluído", "Interrompido")
DESCONECTADO, CONECTANDO, IDENTIFICANDO, CONECTADO, FALHA = (
    "Desconectado", "Conectando", "Identificando", "Conectado", "Falha")


class ComandoProibido(Exception):
    """Comando fora do que esta etapa permite (só leitura)."""


class Conexao:
    def __init__(self, transporte, espera_boot_s=2.5, timeout_s=4.0, intervalo_status_s=0.25):
        self.tr = transporte
        self.espera_boot_s, self.timeout_s, self.intervalo_status_s = espera_boot_s, timeout_s, intervalo_status_s
        self.estado = DESCONECTADO
        self.erro = ""
        self.info = grbl.MaquinaInfo()
        self.status = None
        self.log = []          # (sentido, texto): "→" enviado, "←" recebido, "•" evento (só os últimos 500)
        self.n_log = 0         # quantas entradas já houve (a interface mostra as novas mesmo depois do corte)
        self.trava = threading.RLock()  # a serial lê numa thread própria: estado mexido por uma de cada vez
        self.reinicios = 0
        self._fila = []        # consultas a enviar
        self._atual = None     # consulta aguardando "ok"
        self._t = 0.0          # tempo na fase atual
        self._t_status = 0.0
        self._pediu_status = False
        self.controle = False          # liberado pelo usuário (mover/enviar); parar é sempre permitido
        self.wco = (0.0, 0.0, 0.0)     # deslocamento da origem do trabalho (GRBL manda de tempos em tempos)
        self._desbloquear_apos_parar = False
        self.ar_maquina = None          # air assist (M8) segundo a própria máquina; None = ainda não informou
        self.ultimo_erro_comando = ""   # ex.: "error:9" num jog recusado (alarme)
        self._job, self._job_i, self._job_pend = [], 0, deque()
        self.trabalho, self.trabalho_ok = TRABALHO_PARADO, 0

    # ---------- comandos ----------
    def conectar(self):
        self.erro, self.info, self.status = "", grbl.MaquinaInfo(), None
        try:
            self.tr.abrir()
        except TransporteErro as e:
            return self._falha(f"Não foi possível abrir a porta: {e}")
        self.estado, self._t, self._pediu_status = CONECTANDO, 0.0, False
        self._evento(f"Porta aberta: {getattr(self.tr, 'nome', '')}")

    def desconectar(self):
        try:
            self.tr.fechar()
        finally:
            self.estado, self._fila, self._atual = DESCONECTADO, [], None
            self._evento("Desconectado pelo usuário.")

    # ---------- controle (só depois de liberado) ----------
    def habilitar_controle(self, on=True):
        if on and self.estado != CONECTADO:
            raise ComandoProibido("Conecte e espere identificar a máquina antes de liberar o controle.")
        self.controle = bool(on)
        self._evento("Controle LIBERADO: o programa pode mover a máquina e ligar o laser."
                     if on else "Controle bloqueado: somente leitura.")

    def _exigir_controle(self, com_trabalho_livre=True):
        if not self.controle or self.estado != CONECTADO:
            raise ComandoProibido("Controle não liberado (ou máquina não conectada).")
        if com_trabalho_livre and self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO):
            raise ComandoProibido("Há um trabalho em andamento: pause/pare antes.")

    def _linha_controle(self, cmd):
        self._exigir_controle()
        if not _CONTROLE.match(cmd):
            raise ComandoProibido(f"Comando de controle não reconhecido: {cmd}")
        self._fila.append(cmd)

    def jog(self, dx=0.0, dy=0.0, feed=3000.0):
        """Move o cabeçote relativo (mm), laser desligado."""
        partes = "".join(f" {e}{v:.3f}" for e, v in (("X", dx), ("Y", dy)) if abs(v) > 1e-9)
        if partes:
            self._linha_controle(f"$J=G91 G21{partes} F{feed:.0f}")

    def ir_para(self, x, y, feed=3000.0):
        """Vai até (x, y) nas coordenadas de trabalho, laser desligado."""
        self._linha_controle(f"$J=G90 G21 X{x:.3f} Y{y:.3f} F{feed:.0f}")

    def enquadrar(self, x0, y0, x1, y1, feed=3000.0):
        """Contorna o retângulo do trabalho com o laser DESLIGADO (jog) e volta ao começo."""
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)):
            self.ir_para(x, y, feed)

    def enquadrar_daqui(self, largura, altura, feed=3000.0):
        """Contorna um retângulo a partir da posição atual (canto inferior esquerdo) e volta."""
        for dx, dy in ((largura, 0), (0, altura), (-largura, 0), (0, -altura)):
            self.jog(dx, dy, feed)

    def ar(self, ligado=True):
        """Air assist: M8 liga, M9 desliga."""
        self._linha_controle("M8" if ligado else "M9")

    def enquadrar_com_laser(self, x0, y0, x1, y1, potencia_pct=1.0, feed=3000.0, s_max=1000, relativo=False):
        """Contorna o retângulo com o laser FRACO (M4: apaga sozinho quando para), para ver onde o feixe vai passar.
        Potência limitada a POT_MAX_ENQUADRAR %. Vai como um mini-trabalho (Pausar/Parar funcionam)."""
        pct = min(max(float(potencia_pct), 0.1), POT_MAX_ENQUADRAR)
        s = max(1, round(pct / 100 * s_max))
        w, h = x1 - x0, y1 - y0
        if relativo:  # a partir da posição atual
            moves = ["G91"] + [f"G1 X{dx:.3f} Y{dy:.3f}" for dx, dy in ((w, 0), (0, h), (-w, 0), (0, -h))] + ["G90"]
        else:
            moves = [f"G0 X{x0:.3f} Y{y0:.3f}"] + [f"G1 X{x:.3f} Y{y:.3f}" for x, y in
                                                  ((x1, y0), (x1, y1), (x0, y1), (x0, y0))]
        texto = "\n".join(["G21", "G90", f"M4 S{s}", f"G1 F{feed:.0f}"] + moves + ["M5 S0"]) + "\n"
        self.iniciar_trabalho(texto)
        self._evento(f"Enquadrando com laser fraco ({pct:g} % = S{s}).")

    def parar_jog(self):
        if self.controle and self.estado == CONECTADO:
            self.tr.escrever(bytes([0x85]))
            self._registrar("→", "[cancelar jog]")

    def desbloquear(self):
        self._linha_controle("$X")

    @property
    def tem_homing(self):
        return bool(self.info.valor(22, 0) or 0)

    def limite_software(self, ligado=True):
        """Grava $20=1 (ou 0): limite de curso por software. Rotativo precisa de 0 (o eixo gira sem fim)."""
        self._linha_controle("$20=1" if ligado else "$20=0")

    def ativar_homing(self, ligado=True):
        """Grava $22=1 (ou 0) no controlador: liga o homing pelos fins de curso. A interface pede confirmação."""
        self._linha_controle("$22=1" if ligado else "$22=0")

    def mira(self, ligada, potencia_pct=1.0, s_max=1000):
        """Ponto de luz fraco e PARADO para posicionar a peça (mesmo com o cabeçote movido à mão). Em modo laser
        o GRBL só acende com G1 ativo: M3 S… + "G1 F…" sem eixos. Desliga com M5."""
        if not ligada:
            self._linha_controle("M5")
            return
        pot = max(0.1, min(float(potencia_pct), MIRA_POT_MAX))
        self._linha_controle(f"M3 S{round(s_max * pot / 100)}")
        self._linha_controle("G1 F1000")

    def laser_ligado(self, ligado, potencia_pct=100.0, s_max=1000):
        """Laser ACESO na potência escolhida (até 100 %), parado ou andando com o jog ($J herda o M3 S…).
        Mesmo truque da mira: M3 S… + "G1 F…" sem eixos. Desliga com M5. A interface pede confirmação."""
        if not ligado:
            self._linha_controle("M5")
            return
        pot = max(0.1, min(float(potencia_pct), 100.0))
        self._linha_controle(f"M3 S{round(s_max * pot / 100)}")
        self._linha_controle("G1 F1000")

    def soltar_motores(self, soltos=True):
        """$1 (tempo dos motores travados parados): 255 = sempre travados; 25 = soltam logo após parar e o
        cabeçote pode ser empurrado com a mão. Fica gravado no controlador."""
        self._linha_controle("$1=25" if soltos else "$1=255")

    def homing(self):
        if not self.tem_homing:
            raise ComandoProibido("Esta máquina está sem homing ($22=0).")
        self._linha_controle("$H")

    def referenciar(self):
        """Homing ($H) e, quando terminar, a posição de referência vira o 0,0 do trabalho (G10 L20 P1 X0 Y0)."""
        self.homing()
        self._zerar_depois_do_home = True

    def definir_origem(self, x=0.0, y=0.0):
        """A posição atual do cabeçote passa a valer (x, y) no trabalho (G10 L20 P1, fica gravado no controlador)."""
        self._linha_controle(f"G10 L20 P1 X{x:.3f} Y{y:.3f}")

    def zerar_origem(self):
        """Volta a origem do trabalho para a origem da máquina (G10 L2 P1 X0 Y0)."""
        self._linha_controle("G10 L2 P1 X0 Y0")

    def pausar(self):
        if self.estado == CONECTADO:
            self.tr.escrever(b"!")
            self._registrar("→", "[pausar]")
            self._apagar_na_pausa = True  # 0x9E quando parar (Hold:0): em M3 a pausa sozinha deixa o laser aceso
            if self.trabalho == TRABALHO_RODANDO:
                self.trabalho = TRABALHO_PAUSADO

    def retomar(self):
        self._exigir_controle(com_trabalho_livre=False)
        self.tr.escrever(b"~")
        self._registrar("→", "[retomar]")
        self._apagar_na_pausa = False
        self._pausa_tent = 0
        if self.trabalho == TRABALHO_PAUSADO:
            self.trabalho = TRABALHO_RODANDO

    def parar(self):
        """PARADA: reset do GRBL (0x18). Sempre permitido: para o movimento e apaga o laser na hora."""
        if self.estado in (DESCONECTADO, FALHA):
            return
        try:
            self.tr.escrever(bytes([0x18]))
        except TransporteErro:
            pass
        self._registrar("→", "[PARAR — reset]")
        # Reset durante movimento deixa o GRBL em ALARME (ALARM:3) e tudo fica travado. Foi o usuário que parou e a
        # máquina não tem homing: assim que ela voltar em alarme, desbloqueia sozinho ($X) para poder mover de novo.
        self._desbloquear_apos_parar = self.controle
        if self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO):
            self.trabalho = TRABALHO_ERRO
            self._evento(f"Trabalho PARADO pelo usuário na linha {self.trabalho_ok} de {len(self._job)}.")
        self._job, self._job_i, self._job_pend, self._fila, self._atual = [], 0, deque(), [], None
        self._reref_fase = None

    # ---------- trabalho ----------
    @staticmethod
    def linhas_do_gcode(texto):
        """Linhas que vão para a máquina: sem comentários e sem linhas vazias; recusa comandos de sistema ($)."""
        out = []
        for ln in texto.splitlines():
            ln = ln.split(";", 1)[0].strip()
            if not ln:
                continue
            if ln.startswith("$") or len(ln) > 80:
                raise ComandoProibido(f"Linha não permitida num trabalho: {ln[:40]}")
            out.append(ln)
        return out

    def iniciar_trabalho(self, texto, referenciar_a_cada_s=None):
        """Envia o trabalho. Com `referenciar_a_cada_s` (máquina com fim de curso), a cada tanto tempo o envio para num
        deslocamento SEM laser, espera a máquina parar, faz o $H e continua da mesma linha: passo perdido não se acumula.
        A origem do trabalho (G54) fica gravada no controlador, então as coordenadas continuam valendo depois do $H."""
        self._exigir_controle()
        if referenciar_a_cada_s and not self.tem_homing:
            raise ComandoProibido("Referenciar durante o trabalho precisa de fim de curso ($22=1).")
        if self._fila or self._atual is not None:
            raise ComandoProibido("Espere os movimentos terminarem.")
        if self.status is not None and self.status.em_alarme:
            raise ComandoProibido("A máquina está em ALARME: desbloqueie antes.")
        linhas = self.linhas_do_gcode(texto)
        if not linhas:
            raise ComandoProibido("Trabalho vazio.")
        self._job, self._job_i, self._job_pend = linhas, 0, deque()
        self.texto_trabalho = texto  # com os comentários: a tela mostra a camada de cada linha
        self.trabalho, self.trabalho_ok, self._esperando_fim = TRABALHO_RODANDO, 0, False
        self._reref_s, self._reref_fase, self._reref_t, self.referencias_no_trabalho = referenciar_a_cada_s, None, 0.0, 0
        self._evento(f"Trabalho iniciado: {len(linhas)} linhas."
                     + (f" Referência a cada {referenciar_a_cada_s / 60:g} min." if referenciar_a_cada_s else ""))

    @property
    def posicao(self):
        """(x, y) do cabeçote nas coordenadas do TRABALHO (as do desenho), ou None se ainda não informada."""
        st = self.status
        if st is None:
            return None
        if st.wpos:
            return st.wpos[0], st.wpos[1]
        if st.mpos:
            return st.mpos[0] - self.wco[0], st.mpos[1] - self.wco[1]
        return None

    @property
    def posicao_maquina(self):
        """(x, y) em coordenadas da MÁQUINA (sem homing: 0,0 = onde o cabeçote estava ao ligar)."""
        st = self.status
        if st is None:
            return None
        if st.mpos:
            return st.mpos[0], st.mpos[1]
        if st.wpos:
            return st.wpos[0] + self.wco[0], st.wpos[1] + self.wco[1]
        return None

    def fora_do_curso(self, x0, y0, x1, y1):
        """Lista de avisos se o retângulo (coordenadas do TRABALHO) sai do curso da máquina ($130/$131), contando a
        origem do trabalho (WCO). Sem homing, o curso conta a partir de onde a máquina foi ligada."""
        lx, ly = self.info.valor(130, None), self.info.valor(131, None)
        if not lx or not ly:
            return []
        ax, ay, bx, by = x0 + self.wco[0], y0 + self.wco[1], x1 + self.wco[0], y1 + self.wco[1]
        av = []
        if ax < -0.5 or ay < -0.5:
            av.append(f"vai para trás/esquerda do ponto onde a máquina foi ligada (até X {ax:.0f}, Y {ay:.0f} mm)")
        if bx > lx + 0.5 or by > ly + 0.5:
            av.append(f"passa do curso de {lx:.0f} × {ly:.0f} mm (até X {bx:.0f}, Y {by:.0f} mm)")
        return av

    @property
    def progresso(self):
        """Linhas aceitas pela máquina / total (o fim de verdade é quando ela volta a Idle)."""
        return self.trabalho_ok / len(self._job) if self._job else 0.0

    def _alimentar_trabalho(self):
        if getattr(self, "_reref_fase", None):
            return  # parado para referenciar
        while self._job_i < len(self._job):
            ln = self._job[self._job_i]
            if (self._reref_s and self._reref_t >= self._reref_s and self.trabalho == TRABALHO_RODANDO
                    and _deslocamento_sem_laser(ln)):
                self._reref_fase = "esvaziar"  # termina o que já está na máquina; o $H sai quando ela ficar Idle
                self._evento("Pausa para referenciar: esperando a máquina terminar o que já recebeu…")
                return
            if sum(self._job_pend) + len(ln) + 1 > RX_BUFFER:
                break
            self.tr.escrever((ln + "\n").encode("ascii"))
            self._job_pend.append(len(ln) + 1)
            self._job_i += 1

    def _resposta_trabalho(self, linha):
        if not self._job_pend:
            return False
        self._job_pend.popleft()
        if linha == "ok":
            self.trabalho_ok += 1  # "ok" = a linha ENTROU no planejador; a máquina ainda pode estar executando
            if self.trabalho_ok >= len(self._job):
                self._esperando_fim = True  # concluído só quando a máquina voltar a Idle (ver _receber/status)
        else:
            n = self.trabalho_ok + 1
            # RESET, não pausa: em M3 (corte) o GRBL pausado (!) deixa o laser ACESO parado, queimando no mesmo
            # ponto. O reset apaga na hora; o trabalho pode ser retomado depois ("Retomar interrompido").
            self.tr.escrever(bytes([0x18]))
            self._registrar("→", "[PARAR — reset por erro]")
            self._desbloquear_apos_parar = self.controle
            self.trabalho = TRABALHO_ERRO
            self._evento(f"Trabalho interrompido: {linha} na linha {n} ({self._job[n - 1][:40]}). Laser apagado "
                         "(reset).")
            self._job_i = len(self._job)  # não envia mais nada
        return True

    def _resposta_referencia(self, linha):
        if linha != "ok":
            self._reref_fase = None
            self.tr.escrever(bytes([0x18]))
            self.trabalho = TRABALHO_ERRO
            self._job_i = len(self._job)
            self._evento(f"Referência no meio do trabalho falhou ({linha}). Trabalho parado na linha "
                         f"{self.trabalho_ok}; use Retomar interrompido depois de conferir os fins de curso.")
        elif self._reref_fase == "home":
            # rearma o laser no modo do trabalho (o S continua o mesmo): a próxima linha é um deslocamento sem laser
            modo = next((ln.split()[0] for ln in reversed(self._job[:self._job_i]) if ln.split()[0] in ("M3", "M4")),
                        None)
            if modo:
                self._reref_fase = "rearmar"
                self.tr.escrever((modo + "\n").encode("ascii"))
                return
            self._reref_fase = None
        else:
            self._reref_fase = None
        if self._reref_fase is None and self.trabalho != TRABALHO_ERRO:
            self._reref_t = 0.0
            self.referencias_no_trabalho += 1
            self._evento(f"Referência feita ({self.referencias_no_trabalho}ª): continuando da linha {self.trabalho_ok + 1}.")
            self._alimentar_trabalho()

    def consultar(self, cmd: str):
        """Agenda uma consulta somente leitura ($I, $$, $G)."""
        if cmd not in PERMITIDOS:
            raise ComandoProibido(f"'{cmd}' não é permitido nesta etapa (somente leitura).")
        self._fila.append(cmd)

    # ---------- ciclo ----------
    def chegou(self, linha):
        """Linha recebida na THREAD de leitura da serial: trata e já manda a próxima linha do trabalho, sem esperar a
        interface (é o que evita a máquina parar no meio do trabalho quando a tela está ocupada)."""
        with self.trava:
            self._receber(grbl.limpar(linha))
            if self.estado == CONECTADO and self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO):
                self._alimentar_trabalho()

    def tick(self, dt: float):
        if self.estado in (DESCONECTADO, FALHA):
            return
        try:
            self.tr.esperar(dt)
            for raw in self.tr.ler_linhas():
                self._receber(grbl.limpar(raw))
            self._t += dt
            self._avancar(dt)
        except TransporteErro as e:
            self._falha(f"Conexão perdida: {e}. Nada será retomado automaticamente.")

    def _avancar(self, dt):
        if self.estado == CONECTANDO:
            if self._t >= self.espera_boot_s and not self._pediu_status:
                self._tempo_real("?")       # placa que não reinicia ao abrir: pergunta o estado
                self._pediu_status = True
            elif self._t >= self.espera_boot_s + self.timeout_s:
                self._falha("Sem resposta do controlador. Confira porta, velocidade (baud) e se é GRBL.")
        elif self.estado == IDENTIFICANDO:
            if self._atual is None and self._fila:
                self._enviar(self._fila.pop(0))
            elif self._atual is None:
                self.estado = CONECTADO
                self._evento("Identificado: controle liberado." if self.controle else
                             "Identificado: somente leitura (nenhum movimento, nenhum laser).")
            elif self._t >= self.timeout_s:
                self._falha(f"Sem resposta para {self._atual}.")
        elif self.estado == CONECTADO:
            if self.trabalho == TRABALHO_RODANDO and getattr(self, "_reref_s", None) and not self._reref_fase:
                self._reref_t += dt
            if getattr(self, "_reref_fase", None) == "home" and self._t >= TIMEOUT_HOMING_S:
                self._resposta_referencia("sem resposta do $H")
            elif self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO):
                self._alimentar_trabalho()
            elif self._atual is None and self._fila:
                self._enviar(self._fila.pop(0))
            elif self._atual is not None and self._t >= (TIMEOUT_HOMING_S if self._atual == "$H" else self.timeout_s):
                self._falha(f"Sem resposta para {self._atual}.")
            self._t_status += dt
            if self._t_status >= self.intervalo_status_s:
                self._t_status = 0.0
                self._tempo_real("?")

    def _identificar(self):
        self.estado, self._t = IDENTIFICANDO, 0.0
        self._fila = ["$I", "$$"] + [c for c in self._fila if c not in ("$I", "$$")]
        self._atual = None
        self._tempo_real("?")

    # ---------- recepção ----------
    def _receber(self, linha):
        if not linha:
            return
        if not (linha == "ok" and self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO)):
            self._registrar("←", linha)  # os milhares de "ok" do trabalho não entram (pesavam na tela)
        bv = grbl.boas_vindas(linha)
        if bv:
            if self.estado == CONECTADO:
                self.reinicios += 1
                self._evento("Controlador reiniciou (botão, energia ou reset). Nada foi retomado; reidentificando.")
            self.info.firmware, self.info.detalhe = bv
            if self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO):
                self.trabalho = TRABALHO_ERRO
                self._evento("Controlador reiniciou durante o trabalho: nada foi retomado.")
            self._job, self._job_i, self._job_pend, self._reref_fase = [], 0, deque(), None
            self._identificar()
            return
        st = grbl.status(linha)
        if st:
            self.status = st
            if getattr(self, "_apagar_na_pausa", False) and st.estado == "Hold:0":
                self._apagar_na_pausa = False
                self.tr.escrever(bytes([0x9E]))  # GRBL 1.1: apaga o laser na pausa; o "~" religa ao retomar
                self._registrar("→", "[apagar laser na pausa]")
                self._pausa_tent, self._pausa_espera = 1, 0
            elif self.trabalho == TRABALHO_PAUSADO and st.estado == "Hold:0" and "Ov" in st.campos \
                    and getattr(self, "_pausa_tent", 0):
                # Confere: o GRBL só manda "A:" com S/C se o laser/spindle ainda está ligado. 0x9E é um liga/desliga,
                # então só repete com o laser comprovadamente aceso; se não apagar, reset (laser parado queima o material).
                self._pausa_espera += 1
                if not set(st.campos.get("A", "")) & {"S", "C"}:
                    self._pausa_tent = 0
                elif self._pausa_espera < 3:  # dá 2 relatórios para o comando anterior fazer efeito
                    pass
                elif self._pausa_tent < 3:
                    self._pausa_tent += 1
                    self._pausa_espera = 0
                    self.tr.escrever(bytes([0x9E]))
                    self._registrar("→", "[apagar laser na pausa — de novo]")
                else:
                    self._pausa_tent = 0
                    self._evento("O controlador não apagou o laser na pausa: parei o trabalho (reset) para não queimar. "
                                 "Use 'Retomar interrompido' para continuar.")
                    self.parar()
            if "A" in st.campos or "Ov" in st.campos:  # o GRBL só manda "A:" junto do "Ov:", e só se algo ligou
                self.ar_maquina = "F" in st.campos.get("A", "")
            if self._desbloquear_apos_parar and self.estado == CONECTADO:
                if st.em_alarme and self.controle and not self._fila and self._atual is None:
                    self._desbloquear_apos_parar = False
                    self._fila.append("$X")
                    self._evento("Alarme depois do Parar (normal no GRBL): desbloqueado automaticamente.")
                elif st.estado == "Idle":
                    self._desbloquear_apos_parar = False  # parou sem alarme: nada a fazer
            if "WCO" in st.campos:
                w = grbl._nums(st.campos["WCO"])
                if w:
                    self.wco = w
            if (getattr(self, "_reref_fase", None) == "esvaziar" and not self._job_pend and st.estado == "Idle"
                    and self.trabalho == TRABALHO_RODANDO):
                self._reref_fase, self._t = "home", 0.0
                self.tr.escrever(b"$H\n")
                self._registrar("→", "$H (referência no meio do trabalho)")
            if getattr(self, "_esperando_fim", False) and st.estado == "Idle" and self.trabalho == TRABALHO_RODANDO:
                self._esperando_fim = False
                self.trabalho = TRABALHO_FIM
                self._evento(f"Trabalho concluído ({len(self._job)} linhas).")
                self._job, self._job_i = [], 0
            if self.estado == CONECTANDO:  # respondeu a "?" sem ter reiniciado
                self._identificar()
            return
        cfg = grbl.configuracao(linha)
        if cfg:
            self.info.config[cfg[0]] = cfg[1]
            return
        if linha.startswith("[VER:"):
            self.info.versao = linha[5:-1]
        elif linha.startswith("[OPT:"):
            self.info.opcoes = linha[5:-1]
        elif linha == "ok" or linha.startswith("error:"):
            if getattr(self, "_reref_fase", None) in ("home", "rearmar") and not self._job_pend:
                self._resposta_referencia(linha)
                return
            if self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO) and self._resposta_trabalho(linha):
                return
            if self._atual is not None:
                if linha == "ok" and re.match(r"^\$\d+=", self._atual):
                    k, v = self._atual[1:].split("=")
                    self.info.config[int(k)] = float(v)  # a configuração mudou no controlador
                if self._atual == "$H":
                    if linha == "ok":
                        self._evento("Referência feita (fins de curso).")
                        if getattr(self, "_zerar_depois_do_home", False):
                            self._fila.insert(0, "G10 L20 P1 X0.000 Y0.000")
                            self._evento("Posição de referência = 0,0 do trabalho.")
                    self._zerar_depois_do_home = False
                if linha != "ok":
                    self.ultimo_erro_comando = linha
                    dica = (" — a máquina está em ALARME: clique em Desbloquear." if linha in ("error:9", "error:8")
                            else "")
                    self._evento(f"{self._atual} respondeu {linha}{dica}")
                else:
                    self.ultimo_erro_comando = ""
                self._atual, self._t = None, 0.0
        elif linha.startswith("ALARM:"):
            self._reref_fase = None  # ex.: ALARM:9 = o $H não achou o fim de curso
            if self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO):
                self.trabalho = TRABALHO_ERRO
                self._job_i = len(self._job)
            self._evento(f"Controlador em alarme ({linha})."
                         + (" Use \"Desbloquear\" depois de conferir a máquina." if self.controle else
                            " Libere o controle para desbloquear."))

    # ---------- envio ----------
    def _enviar(self, cmd):
        if cmd not in PERMITIDOS and not (self.controle and _CONTROLE.match(cmd)):  # defesa em profundidade
            raise ComandoProibido(cmd)
        self.tr.escrever((cmd + "\n").encode("ascii"))
        self._registrar("→", cmd)
        self._atual, self._t = cmd, 0.0

    def _tempo_real(self, c):
        if c != "?":
            raise ComandoProibido(c)
        self.tr.escrever(b"?")

    def _evento(self, texto):
        self._registrar("•", texto)

    def _registrar(self, sentido, texto):
        self.log.append((sentido, texto))
        self.n_log += 1
        if len(self.log) > 600:
            del self.log[:-500]  # mantém só o fim do registro

    def _falha(self, msg):
        self.erro = msg
        self.estado = FALHA
        self._fila, self._atual = [], None
        self._evento(msg)
        try:
            self.tr.fechar()
        except TransporteErro:
            pass


def _deslocamento_sem_laser(ln):
    """Ponto seguro para parar e referenciar: G0 (laser apagado no modo laser) ou G1 com S0."""
    p = ln.split()
    return bool(p) and (p[0] == "G0" or (p[0] == "G1" and "S0" in p[1:]))


def _com_trava(f):
    def g(self, *a, **k):
        with self.trava:
            return f(self, *a, **k)
    g.__name__, g.__doc__ = f.__name__, f.__doc__
    return g


# Tudo o que a interface chama (conectar, mover, enviar, pausar, parar, tick...) passa pela mesma trava que a thread
# da serial usa em chegou(): uma de cada vez, sem estado pela metade.
for _nome, _f in list(vars(Conexao).items()):
    if callable(_f) and not _nome.startswith("_") and _nome not in ("chegou", "linhas_do_gcode"):
        setattr(Conexao, _nome, _com_trava(_f))
