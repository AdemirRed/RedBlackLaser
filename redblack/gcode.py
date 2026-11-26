"""G-code GRBL para trabalhos vetoriais (Etapa 11). Gera TEXTO; não envia nada a nenhuma máquina.

Perfil padrão = GRBL 1.1 genérico, NÃO confirmado na SCULPFUN S30 Pro Max:
  - comando de laser M3 (o fabricante orienta "GRBL-M3" no LightBurn); M4 disponível;
  - potência S de 0 a s_max (GRBL $30 padrão = 1000); modo laser ($32=1) é PRÉ-REQUISITO: nele o
    G0 desliga o feixe; sem ele o laser ficaria ligado nos deslocamentos (por isso o cabeçalho avisa);
  - área de trabalho e velocidade máxima do perfil são demonstrativas até serem lidas da máquina.

Coordenadas de máquina: mm absolutos (G21 G90), origem no canto de g.ORIGEM (padrão inferior esquerdo,
Y para cima): ver doc_para_maquina().

Saída determinística: mesmo documento + mesmo perfil = mesmos bytes (sem data/hora).
Air assist: M8 liga e M9 desliga, por camada (opção "Ar" da camada); sempre desligado no fim.
"""
import math
import os
import re
from dataclasses import dataclass

from . import __version__
from . import camadas as cm
from . import geometria as g

EPS = 1e-9


class GcodeInvalido(Exception):
    """Não foi possível gerar com segurança; a mensagem é exibida ao usuário."""


@dataclass(frozen=True)
class PerfilGrbl:
    nome: str = "GRBL genérico (NÃO confirmado na máquina)"
    largura_mm: float | None = None  # None = mesa atual (g.BED_W/g.BED_H, Configurações da máquina)
    altura_mm: float | None = None
    s_max: int = 1000            # GRBL $30
    f_max_mm_min: float = 20000  # SUPOSIÇÃO; GRBL $110/$111 reais vêm da máquina (Etapa 13)
    comando: str = "M3"          # "M3" (potência constante) ou "M4" (dinâmica)
    corte_m3: bool = True        # com perfil M4: camadas de CORTE (linha) saem em M3 (potência constante, como LaserGRBL)
    comp_x_desconto: float = 0.0  # Compensação X: mm/min a menos nos cortes em X (0 = desligada)
    comp_x_minimo: float = 150.0  # …mas nunca abaixo desta velocidade (trabalhos lentos)
    casas: int = 3
    confirmado: bool = False


PERFIL_PADRAO = PerfilGrbl()
CORTE_POT_MIN = 50.0  # % — camada em Linha a partir daqui é CORTE (M3 com corte_m3); abaixo é gravação de linha (M4)
SALTO_GRAVACAO_MM = 30.0  # pulos de gravação até isto viram G1 S0 na velocidade da camada (não G0)
_ORIGEM_TXT = {"inf_esq": "inferior esquerda", "sup_esq": "superior esquerda", "inf_dir": "inferior direita",
               "sup_dir": "superior direita"}
PERFIL = PERFIL_PADRAO  # perfil em uso; muda por Configurações da máquina -> definir_perfil()
F_MAX_LIMITE = 200000.0


def definir_perfil(comando: str = "M3", s_max: int = 1000, f_max_mm_min: float = 20000, corte_m3: bool = True) -> None:
    global PERFIL
    if comando not in ("M3", "M4") or not 1 <= s_max <= 100000 or not 1 <= f_max_mm_min <= F_MAX_LIMITE:
        raise ValueError("perfil inválido")
    PERFIL = PerfilGrbl(comando=comando, s_max=int(s_max), f_max_mm_min=float(f_max_mm_min), corte_m3=bool(corte_m3),
                        comp_x_desconto=PERFIL.comp_x_desconto,  # a compensação X continua valendo
                        comp_x_minimo=PERFIL.comp_x_minimo)


COMP_X_MINIMO_ABS = 10.0  # mm/min: piso absoluto (nunca zero nem negativo)


def definir_comp_x(desconto: float = 0.0, minimo: float = 150.0) -> None:
    """Compensação do eixo X nos CORTES: desconta `desconto` mm/min da velocidade nos trechos em X (gradual nas
    diagonais), sem passar abaixo de `minimo`. desconto 0 = desligada."""
    global PERFIL
    desconto, minimo = float(desconto), float(minimo)
    if not 0 <= desconto <= 10000 or not COMP_X_MINIMO_ABS <= minimo <= 10000:
        raise ValueError(f"desconto de 0 a 10000 mm/min e mínimo de {COMP_X_MINIMO_ABS:g} a 10000 mm/min")
    from dataclasses import replace
    PERFIL = replace(PERFIL, comp_x_desconto=desconto, comp_x_minimo=minimo)


def peso_x(dx: float, dy: float) -> float:
    """Quanto o trecho (dx, dy) é "eixo X": 1 em X puro, 0 em Y puro, cos² no meio (45° = 0,5)."""
    L2 = dx * dx + dy * dy
    return dx * dx / L2 if L2 > 0 else 0.0


def velocidade_compensada(f: float, peso: float, desconto: float, minimo: float) -> float:
    """Velocidade de corte com a compensação X: f − desconto × peso (peso em degraus de 5 % para não trocar F a
    cada trechinho de curva; X puro sai exato), nunca acima de f nem abaixo do mínimo. Se a própria camada já é
    mais lenta que o mínimo, fica como está."""
    if desconto <= 0 or f <= minimo:
        return f
    p = round(min(max(peso, 0.0), 1.0) * 20) / 20
    return max(minimo, f - desconto * p)


def area(perfil: PerfilGrbl) -> tuple[float, float]:
    return (perfil.largura_mm or g.BED_W, perfil.altura_mm or g.BED_H)


def doc_para_maquina(x: float, y: float, W: float, H: float) -> tuple[float, float]:
    """Documento (Y para baixo, origem sup. esq.) -> máquina, conforme o canto da origem (g.ORIGEM)."""
    return (W - x if g.ORIGEM.endswith("dir") else x, y if g.ORIGEM.startswith("sup") else H - y)


def _n(v: float, casas: int) -> str:
    s = f"{v:.{casas}f}"
    return "0." + "0" * casas if s.lstrip("-").strip("0.") == "" else s  # nunca "-0.000"


def gerar(percurso, camadas, perfil: PerfilGrbl | None = None, rotativo=None) -> str:
    """Percurso (Etapa 10) + camadas -> texto G-code. Verifica limites ANTES de produzir qualquer linha."""
    perfil = perfil or PERFIL
    if perfil.comando not in ("M3", "M4"):
        raise GcodeInvalido(f"Comando de laser inválido no perfil: {perfil.comando}")
    if not percurso.trechos:
        raise GcodeInvalido("Nada para gerar: nenhum objeto em camada com Saída ligada.")
    camadas = cm.expandir(camadas)
    por_id = {c.id: c for c in camadas}
    W, H = area(perfil)

    tfy = None
    if rotativo is not None and rotativo.ativo:  # Y vira o eixo do rotativo (ver rotativo.py)
        from . import rotativo as rot
        ys = [doc_para_maquina(*p, W, H)[1] for t in percurso.trechos if t.tipo != "vazio" for p in t.pontos] or [0.0]
        tfy = rot.transformar_y(ys, rotativo)
        volta_inicio = min(ys)  # começo do trabalho no eixo que gira (tfy(min) = min)

    def maquina(p):
        x, y = doc_para_maquina(p[0], p[1], W, H)
        if tfy is None:
            return (x, y)
        # rotativo no X: a volta (Y do desenho) sai no eixo X e o comprimento da peça (X do desenho) sai no Y
        return (tfy(y), x) if rotativo.eixo == "X" else (x, tfy(y))

    # ---- verificações (nada é escrito se algo falhar) ----
    def dentro(m):  # com rotativo o eixo gira sem fim: só X é limitado pela mesa
        if tfy is not None and rotativo.eixo == "X":
            return -EPS <= m[1] <= H + EPS
        return -EPS <= m[0] <= W + EPS and (tfy is not None or -EPS <= m[1] <= H + EPS)

    fora = [m for t in percurso.trechos for m in map(maquina, t.pontos) if not dentro(m)]
    if fora:
        xs, ys = [p[0] for p in fora], [p[1] for p in fora]
        raise GcodeInvalido(f"Percurso fora da área de trabalho ({W:g} × {H:g} mm): {len(fora)} ponto(s), "
                            f"X de {min(xs):.2f} a {max(xs):.2f}, Y de {min(ys):.2f} a {max(ys):.2f} mm. "
                            "Mova ou reduza os objetos.")
    for t in percurso.trechos:
        if t.tipo != "corte":
            continue
        c = por_id.get(t.camada)
        if c is None:
            raise GcodeInvalido(f"Camada {t.camada} sem parâmetros.")
        if c.velocidade_mm_min > perfil.f_max_mm_min:
            raise GcodeInvalido(f"Camada {c.id}: velocidade {c.velocidade_mm_min:g} mm/min acima do máximo do "
                                f"perfil ({perfil.f_max_mm_min:g} mm/min).")
        if not 0 <= c.potencia_max <= 100:
            raise GcodeInvalido(f"Camada {c.id}: potência fora de 0–100 %.")

    # ---- texto ----
    k = perfil.casas
    out = [
        f"; RedBlack Laser {__version__} — G-code GRBL",
        f"; Perfil: {perfil.nome}",
        f"; Area de trabalho: {W:g} x {H:g} mm; origem {_ORIGEM_TXT[g.ORIGEM]}; unidades mm; coordenadas absolutas",
        f"; Laser: {perfil.comando}, S 0-{perfil.s_max}. EXIGE modo laser do GRBL ($32=1): G0 apaga o feixe.",
        "; Air assist: M8 liga / M9 desliga conforme a camada (sempre M9 no fim).",
    ]
    if not perfil.confirmado:
        out.append("; ATENCAO: perfil NAO confirmado na maquina. Confira antes de qualquer execucao.")
    if perfil.comp_x_desconto > 0:
        out.append(f"; COMPENSACAO X ATIVA: cortes em X a velocidade - {perfil.comp_x_desconto:g} mm/min "
                   f"(minimo {perfil.comp_x_minimo:g}); so velocidade, potencia e geometria iguais")
    if tfy is not None:
        out.append(f"; ROTATIVO ({rotativo.tipo}): motor no eixo {rotativo.eixo}, volta multiplicada por {rotativo.fator:.6f} "
                   f"({rotativo.mm_por_rotacao:g} mm/volta, diametro {rotativo.diametro_referencia:g} mm"
                   f"{', espelhado' if rotativo.espelhar else ''}). NAO validado na maquina.")
    out += ["G21 ; milimetros", "G90 ; coordenadas absolutas", "M5 ; laser desligado",
            f"{perfil.comando} S0 ; modo laser armado com potencia zero"]
    camada_atual, s_atual, f_atual, ar_atual = None, None, None, False
    cmd_atual = perfil.comando
    ultimo = percurso.trechos[-1]
    ki = 1 if (tfy is not None and rotativo.eixo == "Y") else 0  # índice do eixo que gira nos pontos de saída

    def teto_giro(a, b, f):
        """Rotativo: F que deixa o eixo que gira no máximo em vel_giro_max (a peça não patina)."""
        if tfy is None or a is None:
            return f
        d_rot = abs(b[ki] - a[ki])
        if d_rot < 1e-6:
            return f
        return max(10.0, min(f, round(rotativo.vel_giro_max * math.hypot(b[0] - a[0], b[1] - a[1]) / d_rot)))

    pos = None  # último ponto escrito (saída)
    for t in percurso.trechos:
        pts = [maquina(p) for p in t.pontos]
        if t.tipo == "vazio" and tfy is not None:
            # deslocamento com rotativo: G1 sem laser e com teto de velocidade (G0 vai no máximo do GRBL e a peça
            # patina; cada patinada tira a gravação do lugar)
            fx, fy = pts[-1]
            fim = t is ultimo
            if fim:  # volta final: só até o começo do trabalho, não até o "Y0 da mesa" escalado
                fx, fy = (fx, volta_inicio) if rotativo.eixo == "Y" else (volta_inicio, fy)
            fv = teto_giro(pos, (fx, fy), perfil.f_max_mm_min) if pos is not None else rotativo.vel_giro_max
            out.append(f"G1 X{_n(fx, k)} Y{_n(fy, k)} S0 F{fv:g}" + (" ; rotativo volta ao inicio do trabalho"
                                                                      if fim else ""))
            s_atual, f_atual, pos = 0, fv, (fx, fy)
            continue
        if (t.tipo == "vazio" and pos is not None and camada_atual in por_id
                and por_id[camada_atual].modo == "preenchimento"
                and math.hypot(pts[-1][0] - pos[0], pts[-1][1] - pos[1]) <= SALTO_GRAVACAO_MM):
            # pulo curto dentro da gravação: G1 sem laser na velocidade da camada. Milhares de G0 (velocidade máxima
            # do GRBL, vai-e-volta) fazem o motor perder passo: depois de 1 h a imagem "escorre" e bate no limite.
            f = por_id[camada_atual].velocidade_mm_min
            out.append(f"G1 X{_n(pts[-1][0], k)} Y{_n(pts[-1][1], k)} S0" + (f" F{f:g}" if f != f_atual else ""))
            s_atual, f_atual, pos = 0, f, pts[-1]
            continue
        if t.tipo == "vazio":
            out.append(f"G0 X{_n(pts[-1][0], k)} Y{_n(pts[-1][1], k)}")
            pos = pts[-1]
            continue
        if t.tipo == "sobra":  # sobrevarredura: anda na velocidade da camada com o laser em zero
            f = teto_giro(pos, pts[-1], por_id[t.camada].velocidade_mm_min)
            out.append(f"G1 X{_n(pts[-1][0], k)} Y{_n(pts[-1][1], k)} S0" + (f" F{f:g}" if f != f_atual else ""))
            s_atual, f_atual, pos = 0, f, pts[-1]
            continue
        c = por_id[t.camada]
        if t.camada != camada_atual:
            out.append(f"; Camada {c.id} ({c.nome}): {c.modo}, {c.velocidade_mm_min:g} mm/min, "
                       f"{c.potencia_max:g} %, {c.passadas} passada(s)")
            camada_atual = t.camada
            # Corte com M4 perde potência onde o cabeçote desacelera (cantos, começo/fim de linha) e pode não varar
            # a chapa: com corte_m3, camadas em Linha saem em M3 (constante); gravação continua no modo do perfil.
            # Linha fraca (< CORTE_POT_MIN, ex.: divisas e marcações gravadas) é gravação: fica em M4, senão queima mais
            # onde o cabeçote freia (cantos e pontas viram pontinhos).
            cmd = ("M3" if (perfil.comando == "M4" and perfil.corte_m3 and c.modo == "linha"
                            and c.potencia_max >= CORTE_POT_MIN) else perfil.comando)
            if cmd != cmd_atual:
                out.append(f"{cmd} S0 ; {'potencia constante (corte)' if cmd == 'M3' else 'potencia dinamica'}")
                cmd_atual, s_atual = cmd, 0
            if bool(c.air) != ar_atual:
                ar_atual = bool(c.air)
                out.append("M8 ; air assist ligado" if ar_atual else "M9 ; air assist desligado")
        s = round((c.potencia_max if t.potencia is None else t.potencia) / 100 * perfil.s_max)
        f = c.velocidade_mm_min
        comp = perfil.comp_x_desconto > 0 and c.modo == "linha" and s > 0  # só cortes com laser, só velocidade
        jx = jy = 0.0  # direção suavizada (soma dos trechos dos últimos ~2 mm): curvas não fazem F pular
        for i, (x, y) in enumerate(pts[1:]):
            line = f"G1 X{_n(x, k)} Y{_n(y, k)}"
            if i == 0 and s != s_atual:
                line += f" S{s}"
                s_atual = s
            fi = f
            if comp:
                dx, dy = x - pts[i][0], y - pts[i][1]
                seg = math.hypot(dx, dy)
                if seg > 0:
                    peso = min(1.0, seg / 2.0)
                    jx, jy = jx * (1 - peso) + abs(dx) / seg * peso, jy * (1 - peso) + abs(dy) / seg * peso
                    fi = velocidade_compensada(f, peso_x(jx, jy), perfil.comp_x_desconto, perfil.comp_x_minimo)
            if tfy is not None:
                # rotativo: o eixo que gira anda `fator` × a distância na superfície; o F vale para a distância de
                # comando, então sem isto o trecho em volta da peça ficava mais lento (queimava mais) que o reto
                sup = math.hypot(t.pontos[i + 1][0] - t.pontos[i][0], t.pontos[i + 1][1] - t.pontos[i][1])
                cmd_d = math.hypot(x - pts[i][0], y - pts[i][1])
                if sup > 1e-9 and abs(cmd_d - sup) > 1e-6:
                    fi = min(perfil.f_max_mm_min, max(10.0, round(fi * cmd_d / sup / 10) * 10))
                fi = teto_giro(pts[i], (x, y), fi)
            if fi != f_atual:
                line += f" F{fi:g}"
                f_atual = fi
            out.append(line)
        pos = pts[-1]
    out += ["M5 ; laser desligado"] + (["M9 ; air assist desligado"] if ar_atual else []) + ["M2 ; fim do programa"]
    return "\n".join(out) + "\n"


def salvar(path: str, texto: str) -> None:
    """Grava atomicamente (temporário + substituição): falha no meio não deixa arquivo pela metade."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ---------- verificação (lê o G-code de volta, sem máquina) ----------
_WORD = re.compile(r"([A-Z])([-+]?\d*\.?\d+)")


def analisar(texto: str, perfil: PerfilGrbl | None = None) -> dict:
    """Interpreta o subconjunto gerado acima e devolve medidas para conferência.

    Recusa comandos fora do subconjunto, polegadas (G20), relativo (G91) e movimento com laser
    ligado fora de G1. Considera o laser emitindo só em G1 com S > 0 após M3/M4 (modo laser).
    """
    W, H = area(perfil or PERFIL)
    x = y = 0.0
    s, f, laser, absoluto, mm = 0, None, False, False, False
    corte = vazio = 0.0
    xs, ys = [0.0], [0.0]
    s_max_visto = 0
    for n, raw in enumerate(texto.splitlines(), 1):
        line = raw.split(";", 1)[0].strip().upper()
        if not line:
            continue
        words = dict((a, float(b)) for a, b in _WORD.findall(line))
        cmd = line.split()[0]
        if cmd == "G21":
            mm = True
        elif cmd == "G20":
            raise GcodeInvalido(f"Linha {n}: polegadas (G20) não permitidas.")
        elif cmd == "G90":
            absoluto = True
        elif cmd == "G91":
            raise GcodeInvalido(f"Linha {n}: coordenadas relativas (G91) não permitidas.")
        elif cmd in ("M3", "M4"):
            laser, s = True, int(words.get("S", s))
        elif cmd in ("M5", "M2"):
            laser = False
        elif cmd in ("M8", "M9"):  # air assist liga/desliga: não muda posição nem laser
            pass
        elif cmd in ("G0", "G1"):
            if not (mm and absoluto):
                raise GcodeInvalido(f"Linha {n}: movimento antes de G21/G90.")
            if "S" in words:
                s = int(words["S"])
            if "F" in words:
                f = words["F"]
            nx, ny = words.get("X", x), words.get("Y", y)
            d = math.hypot(nx - x, ny - y)
            if cmd == "G1" and laser and s > 0:
                if f is None:
                    raise GcodeInvalido(f"Linha {n}: corte sem velocidade (F).")
                corte += d
                s_max_visto = max(s_max_visto, s)
            else:
                vazio += d
            x, y = nx, ny
            xs.append(x)
            ys.append(y)
        else:
            raise GcodeInvalido(f"Linha {n}: comando fora do subconjunto suportado: {cmd}")
    return {"comprimento_corte": corte, "comprimento_vazio": vazio, "x": (min(xs), max(xs)),
            "y": (min(ys), max(ys)), "s_max": s_max_visto, "fim_desligado": not laser,
            "dentro_da_area": min(xs) >= -EPS and min(ys) >= -EPS and max(xs) <= W + EPS
            and max(ys) <= H + EPS}


_XY = re.compile(r"([XY])(-?\d+(?:\.\d+)?)")


def deslocar(texto: str, dx: float, dy: float) -> str:
    """Soma (dx, dy) às coordenadas X/Y das linhas G0/G1 (ex.: começar o trabalho na posição atual do cabeçote sem
    mexer na origem guardada no controlador)."""
    out = []
    for ln in texto.splitlines():
        cmd = ln.split(";", 1)[0].strip().split(" ", 1)[0]
        if cmd in ("G0", "G1"):
            ln = _XY.sub(lambda m: f"{m.group(1)}{float(m.group(2)) + (dx if m.group(1) == 'X' else dy):.3f}", ln)
        out.append(ln)
    return "\n".join(out) + "\n"


def ar_no_trabalho_todo(texto: str) -> str:
    """Air assist ligado do começo ao fim (M8 antes do primeiro movimento, M9 só no fim), em qualquer camada."""
    linhas = [ln for ln in texto.splitlines() if ln.split(";", 1)[0].strip() not in ("M8", "M9")]
    cmd = [ln.split(";", 1)[0].strip().split(" ", 1)[0] for ln in linhas]
    i = next((k for k, c in enumerate(cmd) if c in ("G0", "G1")), len(linhas))
    linhas.insert(i, "M8 ; air assist ligado (trabalho todo)")
    fim = max((k for k, c in enumerate(linhas) if c.split(";", 1)[0].strip() == "M2"), default=len(linhas))
    linhas.insert(fim, "M9 ; air assist desligado")
    return chr(10).join(linhas) + chr(10)


_PALAVRA = re.compile(r"([GMXYFS])(-?\d+(?:\.\d+)?)")


def estado_ate(linhas, k):
    """Estado da máquina depois de executar `linhas[:k]` (linhas já sem comentários): posição, avanço, potência,
    modo do laser (M3/M4/M5), ar (M8/M9) e movimento modal (0/1). Para retomar ou começar no meio."""
    st = {"x": 0.0, "y": 0.0, "f": None, "s": 0.0, "laser": "M5", "ar": False, "mov": 0}
    for ln in linhas[:k]:
        for letra, num in _PALAVRA.findall(ln.upper()):
            v = float(num)
            if letra == "G" and v in (0, 1):
                st["mov"] = int(v)
            elif letra == "M":
                m = int(v)
                if m in (3, 4, 5):
                    st["laser"] = f"M{m}"
                elif m in (8, 9):
                    st["ar"] = m == 8
                elif m == 2:
                    st["laser"], st["ar"] = "M5", False
            elif letra == "X":
                st["x"] = v
            elif letra == "Y":
                st["y"] = v
            elif letra == "F":
                st["f"] = v
            elif letra == "S":
                st["s"] = v
    return st


def retomar_de(linhas, k, fim=None):
    """Trabalho que começa na linha `k` (e para antes de `fim`, se dado) com o estado certo: unidades, laser
    desligado no deslocamento até o ponto onde a linha k começa, ar, modo/potência do laser e avanço restaurados.
    Termina sempre com laser e ar desligados."""
    k = max(0, min(int(k), len(linhas)))
    fim = len(linhas) if fim is None else max(k, min(int(fim), len(linhas)))
    st = estado_ate(linhas, k)
    out = ["G21", "G90", "M5"]
    if st["ar"]:
        out.append("M8")
    out.append(f"G0 X{st['x']:.3f} Y{st['y']:.3f}")  # vai ao ponto de partida com o laser apagado
    if st["laser"] in ("M3", "M4"):
        out.append(f"{st['laser']} S{st['s']:g}")
    if st["f"]:
        out.append(f"G{st['mov']} F{st['f']:g}")
    out += list(linhas[k:fim])
    if fim < len(linhas) or not any(ln.split()[0] in ("M2", "M30") for ln in linhas[k:fim] if ln):
        out += ["M5", "M9", "M2"]
    return out
