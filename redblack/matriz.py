"""Matriz de testes de materiais (Etapa 18): grade de quadrados, cada um com potência e velocidade próprias.

Colunas = potência (esquerda → direita, crescente); linhas (topo → base, crescente) = velocidade, intervalo de
linhas ("teste de intervalo") ou passadas — nesses dois últimos casos a velocidade é fixa (vel_min).
Gera o documento da matriz (quadrados + rótulos) e camadas próprias por célula ("Mrrcc"); essas camadas
existem só dentro da matriz e não entram no projeto. Nada é enviado à máquina: o resultado é um G-code.
Depois de gravar, escolha a melhor célula, ponha os valores numa camada e salve como material.
"""
import json
import math
from dataclasses import asdict, dataclass, fields

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath, QTransform

from . import camadas as cm
from . import formas as fm
from . import gcode as gc
from . import materiais as mt
from . import percurso as pc
from . import texto as tx

MAX_LADO = 20
ROTULO_MM = 2.5       # altura dos números
FONTE_ROTULO = "Arial"
MARGEM_ROTULO = 18.0  # espaço à esquerda (velocidades) e acima (potências) reservado aos rótulos


@dataclass(frozen=True)
class Matriz:
    modo: str = "preenchimento"         # "preenchimento" (gravação) ou "linha" (corte/contorno)
    pot_min: float = 10.0
    pot_max: float = 50.0
    colunas: int = 5
    vel_min: float = 1000.0
    vel_max: float = 5000.0
    linhas: int = 5
    celula_mm: float = 10.0
    vao_mm: float = 3.0
    x_mm: float = 30.0                   # canto superior esquerdo da 1ª célula (documento)
    y_mm: float = 30.0
    passadas: int = 1
    intervalo_mm: float = 0.1
    air: bool = True
    rotulos: bool = True
    rotulo_pot: float = 15.0             # rótulos gravados em contorno com estes parâmetros
    rotulo_vel: float = 3000.0
    linhas_param: str = "velocidade"     # o que varia nas linhas: "velocidade" | "intervalo" | "passadas"
    lin_min: float = 0.05                # faixa das linhas quando não é velocidade (mm ou passadas)
    lin_max: float = 0.3
    colunas_param: str = "potencia"      # o que varia nas colunas: "potencia" | "velocidade" (teste de corte)
    pot_fixa: float = 80.0               # potência de todos os quadrados quando as colunas são velocidade
    comando: str = ""                    # "" = o do perfil da máquina; "M3" constante | "M4" dinâmico

    def valores_linhas(self):
        if self.linhas_param == "velocidade":
            return self.velocidades()
        v = _passos(self.lin_min, self.lin_max, self.linhas)
        return [max(1, round(x)) for x in v] if self.linhas_param == "passadas" else v

    def unidade_linhas(self) -> str:
        return {"velocidade": "mm/min", "intervalo": "mm", "passadas": "passadas"}[self.linhas_param]

    def parametros(self, r, c):
        """(velocidade, potência, passadas, intervalo) do quadrado da linha r, coluna c."""
        v = self.valores_linhas()[r]
        if self.colunas_param == "velocidade":  # teste de corte: velocidade nas colunas, potência fixa
            vel, pot = self.valores_colunas()[c], self.pot_fixa
        else:
            vel = v if self.linhas_param == "velocidade" else self.vel_min
            pot = self.potencias()[c]
        passadas = int(v) if self.linhas_param == "passadas" else self.passadas
        intervalo = v if self.linhas_param == "intervalo" else self.intervalo_mm
        return vel, pot, passadas, intervalo

    def potencias(self):
        return _passos(self.pot_min, self.pot_max, self.colunas)

    def valores_colunas(self):
        if self.colunas_param == "velocidade":
            return _passos(self.vel_min, self.vel_max, self.colunas)
        return self.potencias()

    def unidade_colunas(self) -> str:
        return "mm/min" if self.colunas_param == "velocidade" else "%"

    def velocidades(self):
        return _passos(self.vel_min, self.vel_max, self.linhas)

    def celula(self, r, c) -> QRectF:
        p = self.celula_mm + self.vao_mm
        return QRectF(self.x_mm + c * p, self.y_mm + r * p, self.celula_mm, self.celula_mm)

    def limites(self):
        """(x0, y0, x1, y1) incluindo a área dos rótulos."""
        p = self.celula_mm + self.vao_mm
        m = MARGEM_ROTULO if self.rotulos else 0.0
        return (self.x_mm - m, self.y_mm - m, self.x_mm + self.colunas * p - self.vao_mm,
                self.y_mm + self.linhas * p - self.vao_mm)


def _passos(a, b, n):
    return [round(a + (b - a) * i / (n - 1), 2) for i in range(n)] if n > 1 else [a]


def erros(m: Matriz, mesa_w, mesa_h) -> list:
    out = []
    for n in ("colunas", "linhas", "passadas"):
        v = getattr(m, n)
        if isinstance(v, bool) or not isinstance(v, int):
            out.append(f"{n} deve ser inteiro")
    if out:
        return out
    if m.modo not in cm.MODOS_VETOR:
        out.append("modo inválido")
    if not (1 <= m.colunas <= MAX_LADO and 1 <= m.linhas <= MAX_LADO):
        out.append(f"colunas e linhas de 1 a {MAX_LADO}")
    if m.colunas_param not in ("potencia", "velocidade"):
        out.append("parâmetro das colunas inválido")
    if m.comando not in ("", "M3", "M4"):
        out.append("modo do laser inválido")
    if m.colunas_param == "velocidade" and m.linhas_param == "velocidade":
        out.append("velocidade não pode variar nas colunas e nas linhas ao mesmo tempo")
    if m.colunas_param == "velocidade" and m.vel_min > m.vel_max:
        out.append("velocidade inicial maior que a final")
    if m.pot_min > m.pot_max:
        out.append("potência inicial maior que a final")
    if m.linhas_param not in ("velocidade", "intervalo", "passadas"):
        out.append("parâmetro das linhas inválido")
        return out
    if m.linhas_param == "velocidade" and m.vel_min > m.vel_max:
        out.append("velocidade inicial maior que a final")
    if m.linhas_param != "velocidade" and m.lin_min > m.lin_max:
        out.append("valor inicial das linhas maior que o final")
    if not 2 <= m.celula_mm <= 100 or not 0 <= m.vao_mm <= 50:
        out.append("célula de 2 a 100 mm e vão de 0 a 50 mm")
    if not out:
        for r_ in (0, m.linhas - 1):
            for c in (0, m.colunas - 1):
                vel, pot, pas, itv = m.parametros(r_, c)
                out += cm.validar(cm.Camada("C01", "", m.modo, vel, pot, 0.0, pas, itv, air=m.air))
    out += cm.validar(cm.Camada("C01", "", m.modo, m.rotulo_vel, m.rotulo_pot, 0.0, 1, m.intervalo_mm, air=m.air))
    x0, y0, x1, y1 = m.limites()
    if x0 < 0 or y0 < 0 or x1 > mesa_w or y1 > mesa_h:
        out.append(f"a matriz ({x1 - x0:.0f} × {y1 - y0:.0f} mm com rótulos) sai da mesa de "
                   f"{mesa_w:g} × {mesa_h:g} mm")
    return list(dict.fromkeys(out))


def _snap(path, nome, layer):
    return (path, QTransform(), nome, layer, "#ffffff", None)


def _texto(t, cx, cy):
    """Contorno do texto centrado em (cx, cy)."""
    p = tx.build_path(tx.TextoParams(t, FONTE_ROTULO, ROTULO_MM))
    b = p.boundingRect()
    return QTransform.fromTranslate(cx - b.center().x(), cy - b.center().y()).map(p)


def documento(m: Matriz):
    """(snapshots, camadas na ordem de saída). Rótulos primeiro: num corte, as peças só soltam no fim."""
    snaps, camadas = [], []
    if m.rotulos:
        rot = QPainterPath()
        for c, val in enumerate(m.valores_colunas()):
            r = m.celula(0, c)
            rot.addPath(_texto(f"{val:g}".replace(".", ","), r.center().x(), r.top() - 4))
        for r_, val in enumerate(m.valores_linhas()):
            r = m.celula(r_, 0)
            rot.addPath(_texto(f"{val:g}".replace(".", ","), r.left() - 9, r.center().y()))
        rot.addPath(_texto(m.unidade_colunas(), m.celula(0, 0).left() - 9, m.celula(0, 0).top() - 4 - ROTULO_MM - 2))
        rot.addPath(_texto(m.unidade_linhas(), m.celula(0, 0).left() - 9, m.celula(0, 0).top() - 4))
        snaps.append(_snap(rot, "Rótulos da matriz", "MROT"))
        camadas.append(cm.Camada("MROT", "rótulos", "linha", m.rotulo_vel, m.rotulo_pot, 0.0, 1, m.intervalo_mm,
                                 air=m.air))
    for r_ in range(m.linhas):
        for c in range(m.colunas):
            vel, pot, pas, itv = m.parametros(r_, c)
            lid = f"M{r_:02d}{c:02d}"
            nome = f"{pot:g} % / {vel:g} mm/min / {pas} passada(s) / intervalo {itv:g} mm"
            snaps.append(_snap(fm.rect_path(m.celula(r_, c)), nome, lid))
            camadas.append(cm.Camada(lid, nome, m.modo, vel, pot, 0.0, pas, itv, air=m.air))
    return snaps, camadas


def gerar(m: Matriz, perfil: gc.PerfilGrbl | None = None):
    """(texto G-code, Percurso). Recusa matriz inválida antes de produzir texto."""
    e = erros(m, *gc.area(perfil or gc.PERFIL))
    if e:
        raise gc.GcodeInvalido("Matriz inválida: " + "; ".join(e) + ".")
    snaps, camadas = documento(m)
    perc = pc.gerar(snaps, camadas)
    perfil = perfil or gc.PERFIL
    if m.comando in ("M3", "M4"):  # modo do laser escolhido no teste (M3 constante / M4 dinâmico)
        from dataclasses import replace
        perfil = replace(perfil, comando=m.comando)
    texto = gc.gerar(perc, camadas, perfil)
    col = (f"{m.colunas} potencias {m.pot_min:g}-{m.pot_max:g} %" if m.colunas_param == "potencia" else
           f"{m.colunas} velocidades {m.vel_min:g}-{m.vel_max:g} mm/min a {m.pot_fixa:g} %")
    cab = (f"; Matriz de testes: {col} (colunas, esquerda->direita) x "
           f"{m.linhas} {m.linhas_param} {m.valores_linhas()[0]:g}-{m.valores_linhas()[-1]:g} {m.unidade_linhas()} "
           f"(linhas, topo->base); velocidade {m.vel_min:g} se fixa; modo {m.modo}; "
           f"{m.passadas} passada(s)\n")
    # Parâmetros completos numa linha de comentário: a matriz pode ser reaberta a partir do arquivo.
    return cab + MARCA + json.dumps(para_dict(m), ensure_ascii=True) + "\n" + texto, perc


MARCA = "; RBMATRIZ "


def para_dict(m: Matriz) -> dict:
    return asdict(m)


def de_dict(d) -> Matriz:
    """Dados não confiáveis (configurações ou arquivo). ValueError se inválido."""
    nomes = {f.name for f in fields(Matriz)}
    novos = {"linhas_param", "lin_min", "lin_max", "colunas_param", "pot_fixa", "comando"}  # ausentes nas antigas
    if not isinstance(d, dict) or not (set(d) <= nomes and nomes - set(d) <= novos):
        raise ValueError("campos da matriz ausentes ou desconhecidos")
    conv = {}
    for f in fields(Matriz):
        if f.name not in d:
            continue
        v = d[f.name]
        if f.type is bool:
            ok = isinstance(v, bool)
        elif f.type is int:
            ok = isinstance(v, int) and not isinstance(v, bool)
        elif f.type is str:
            ok = isinstance(v, str)
        else:
            ok = isinstance(v, (int, float)) and not isinstance(v, bool)
            v = float(v) if ok else v
        if not ok:
            raise ValueError(f"{f.name} com tipo inválido")
        conv[f.name] = v
    m = Matriz(**conv)
    e = erros(m, math.inf, math.inf)
    if e:
        raise ValueError("; ".join(e))
    return m


def de_gcode(texto: str) -> Matriz:
    """Matriz gravada no cabeçalho de um G-code gerado por esta função. ValueError se não houver."""
    for linha in texto.splitlines()[:20]:
        if linha.startswith(MARCA):
            try:
                return de_dict(json.loads(linha[len(MARCA):]))
            except json.JSONDecodeError as e:
                raise ValueError("parâmetros da matriz corrompidos no arquivo") from e
    raise ValueError("o arquivo não é uma matriz de testes do RedBlack Laser")


def material(m: Matriz, linha: int, coluna: int, nome: str, espessura_mm: float, nota="") -> mt.Material:
    """Preset do usuário com os parâmetros do quadrado escolhido (linha = velocidade, coluna = potência)."""
    if not (0 <= linha < m.linhas and 0 <= coluna < m.colunas):
        raise ValueError("quadrado fora da matriz")
    vel, pot, pas, itv = m.parametros(linha, coluna)
    nota = nota.strip() or (f"Da matriz de testes: {pot:g} % × {vel:g} mm/min, {pas} passada(s), intervalo {itv:g} mm "
                            f"(linha {linha + 1}, coluna {coluna + 1}).")
    mat = mt.Material(nome.strip()[:80], espessura_mm, "corte" if m.modo == "linha" else "gravação", vel, pot,
                      pas, m.air, itv, nota[:200], "meu")
    e = mt.erros(mat)
    if e:
        raise ValueError("; ".join(e))
    return mat


# ---------------------------------------------------------------- teste de precisão (escala e esquadro)
def precisao(x_mm=30.0, y_mm=30.0, lado=100.0, potencia=15.0, velocidade=1500.0):
    """(snapshots, camadas) do teste de precisão: quadrado de `lado`, quadrado de lado/2 e círculo de Ø lado/2 no
    centro, diagonais e régua com traços a cada 10 mm (traço maior a cada 50) nos lados de baixo e da esquerda.
    Meça com paquímetro: o quadrado deve dar `lado` nos dois eixos e as diagonais devem ser iguais (esquadro)."""
    p = QPainterPath()
    q = QRectF(x_mm, y_mm, lado, lado)
    p.addRect(q)
    c = q.center()
    p.addRect(QRectF(c.x() - lado / 4, c.y() - lado / 4, lado / 2, lado / 2))
    p.addEllipse(c, lado / 4, lado / 4)
    p.moveTo(q.topLeft())
    p.lineTo(q.bottomRight())
    p.moveTo(q.topRight())
    p.lineTo(q.bottomLeft())
    n = int(lado // 10)
    for i in range(n + 1):
        t = 4.0 if i % 5 == 0 else 2.0
        x = x_mm + i * 10
        p.moveTo(x, q.bottom())
        p.lineTo(x, q.bottom() + t)
        y = q.bottom() - i * 10
        p.moveTo(x_mm, y)
        p.lineTo(x_mm - t, y)
    rot = QPainterPath()
    rot.addPath(_texto(f"{lado:g} mm", c.x(), q.bottom() + 8))
    rot.addPath(_texto(f"{lado:g}", x_mm - 9, c.y()))
    rot.addPath(_texto(f"Ø{lado / 2:g}", c.x(), c.y() - lado / 4 - 4))
    lay = cm.Camada("MPRE", "teste de precisão", "linha", velocidade, potencia, 0.0, 1, 0.1)
    return [_snap(p, "Teste de precisão", "MPRE"), _snap(rot, "Rótulos", "MPRE")], [lay]


def gerar_precisao(x_mm=30.0, y_mm=30.0, lado=100.0, potencia=15.0, velocidade=1500.0, perfil=None):
    """(texto G-code, Percurso) do teste de precisão; recusa se sair da mesa."""
    W, H = gc.area(perfil or gc.PERFIL)
    if x_mm - 15 < 0 or y_mm < 0 or x_mm + lado > W or y_mm + lado + 12 > H or not 20 <= lado <= 300:
        raise gc.GcodeInvalido(f"Teste de precisão de {lado:g} mm não cabe na mesa ({W:g} × {H:g} mm) nessa posição.")
    snaps, camadas = precisao(x_mm, y_mm, lado, potencia, velocidade)
    perc = pc.gerar(snaps, camadas)
    cab = f"; Teste de precisao: quadrado {lado:g} mm, circulo {lado / 2:g} mm, regua a cada 10 mm" + chr(10)
    return cab + gc.gerar(perc, camadas, perfil), perc

