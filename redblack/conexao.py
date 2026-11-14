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
        self.log = []          # (sentido, texto): "→" enviado, "←" recebido, "•" evento
        self.reinicios = 0
        self._fila = []        # consultas a enviar
        self._atual = None     # consulta aguardando "ok"
        self._t = 0.0          # tempo na fase atual
        self._t_status = 0.0
        self._pediu_status = False
        self.controle = False          # liberado pelo usuário (mover/enviar); parar é sempre permitido
        self.wco = (0.0, 0.0, 0.0)     # deslocamento da origem do trabalho (GRBL manda de tempos em tempos)
        self._desbloquear_apos_parar = False
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
            self.log.append(("→", "[cancelar jog]"))

    def desbloquear(self):
        self._linha_controle("$X")

    @property
    def tem_homing(self):
        return bool(self.info.valor(22, 0) or 0)

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
            self.log.append(("→", "[pausar]"))
            if self.trabalho == TRABALHO_RODANDO:
                self.trabalho = TRABALHO_PAUSADO

    def retomar(self):
        self._exigir_controle(com_trabalho_livre=False)
        self.tr.escrever(b"~")
        self.log.append(("→", "[retomar]"))
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
        self.log.append(("→", "[PARAR — reset]"))
        # Reset durante movimento deixa o GRBL em ALARME (ALARM:3) e tudo fica travado. Foi o usuário que parou e a
        # máquina não tem homing: assim que ela voltar em alarme, desbloqueia sozinho ($X) para poder mover de novo.
        self._desbloquear_apos_parar = self.controle
        if self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO):
            self.trabalho = TRABALHO_ERRO
            self._evento(f"Trabalho PARADO pelo usuário na linha {self.trabalho_ok} de {len(self._job)}.")
        self._job, self._job_i, self._job_pend, self._fila, self._atual = [], 0, deque(), [], None

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

    def iniciar_trabalho(self, texto):
        self._exigir_controle()
        if self._fila or self._atual is not None:
            raise ComandoProibido("Espere os movimentos terminarem.")
        if self.status is not None and self.status.em_alarme:
            raise ComandoProibido("A máquina está em ALARME: desbloqueie antes.")
        linhas = self.linhas_do_gcode(texto)
        if not linhas:
            raise ComandoProibido("Trabalho vazio.")
        self._job, self._job_i, self._job_pend = linhas, 0, deque()
        self.trabalho, self.trabalho_ok, self._esperando_fim = TRABALHO_RODANDO, 0, False
        self._evento(f"Trabalho iniciado: {len(linhas)} linhas.")

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
        while self._job_i < len(self._job):
            ln = self._job[self._job_i]
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
            self.tr.escrever(b"!")  # pausa já: não continua gravando depois de um erro
            self.trabalho = TRABALHO_ERRO
            self._evento(f"Trabalho interrompido: {linha} na linha {n} ({self._job[n - 1][:40]}). Máquina pausada; "
                         "use Parar.")
            self._job_i = len(self._job)  # não envia mais nada
        return True

    def consultar(self, cmd: str):
        """Agenda uma consulta somente leitura ($I, $$, $G)."""
        if cmd not in PERMITIDOS:
            raise ComandoProibido(f"'{cmd}' não é permitido nesta etapa (somente leitura).")
        self._fila.append(cmd)

    # ---------- ciclo ----------
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
            if self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO):
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
        self.log.append(("←", linha))
        bv = grbl.boas_vindas(linha)
        if bv:
            if self.estado == CONECTADO:
                self.reinicios += 1
                self._evento("Controlador reiniciou (botão, energia ou reset). Nada foi retomado; reidentificando.")
            self.info.firmware, self.info.detalhe = bv
            if self.trabalho in (TRABALHO_RODANDO, TRABALHO_PAUSADO):
                self.trabalho = TRABALHO_ERRO
                self._evento("Controlador reiniciou durante o trabalho: nada foi retomado.")
            self._job, self._job_i, self._job_pend = [], 0, deque()
            self._identificar()
            return
        st = grbl.status(linha)
        if st:
            self.status = st
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
        self.log.append(("→", cmd))
        self._atual, self._t = cmd, 0.0

    def _tempo_real(self, c):
        if c != "?":
            raise ComandoProibido(c)
        self.tr.escrever(b"?")

    def _evento(self, texto):
        self.log.append(("•", texto))
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
