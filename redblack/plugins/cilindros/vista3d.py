"""Visualização 3D do copo (malha de revolução) com a arte aplicada, desenhada só com QPainter (funciona em
qualquer PC). Botão esquerdo gira a vista, direito (ou Shift+esquerdo) move a arte, roda aproxima.

A arte é aplicada como o rotativo grava: a largura dela corre em volta da peça por ângulo (raio do meio da arte),
a altura desce a partir de "Arte começa abaixo da boca". Arte com largura = circunferência dá a volta inteira (360°).
A emenda da malha fica do lado oposto do centro da arte."""
import dataclasses
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import QWidget

from . import calc

MATERIAIS = {  # nome: (cor do copo padrão, cor da gravação padrão, brilho)
    "Copo pintado / térmico (gravação revela o inox)": ("#1d1e21", "#b4b8be", 0.35),
    "Inox sem pintura (gravação escurece)": ("#b9bec4", "#55585d", 0.55),
    "Alumínio anodizado (gravação fica clara)": ("#2b4f9e", "#e3e6ea", 0.45),
    "Madeira / bambu (gravação queimada)": ("#c79a62", "#4a2a12", 0.1),
    "Couro (gravação queimada)": ("#8b5a2b", "#3b2414", 0.15),
    "Vidro / cristal (gravação jateada)": ("#9fb7c4", "#f2f5f7", 0.6),
}


def malha(p: calc.Peca, angulo_arte=0.0, n_ang=96, n_alt=None):
    """Pontos da superfície: lista de linhas (de cima para baixo) com (x, y, z, θ relativo à arte, raio, z_mm).
    θ vai de −π a +π em volta do centro da arte (a emenda fica atrás)."""
    phi = math.radians(angulo_arte)
    n_alt = n_alt or (36 if len(calc.nos(p)) <= 2 else 72)  # perfil com pontos (taça): mais linhas
    linhas = []
    for i in range(n_alt + 1):
        z = p.altura * i / n_alt
        r = calc.diametro_em(p, z) / 2
        lin = []
        for j in range(n_ang + 1):
            t = -math.pi + 2 * math.pi * j / n_ang
            a = phi + t
            lin.append((r * math.sin(a), -r * math.cos(a), -z, t, r, z))
        linhas.append(lin)
    return linhas


def raio_rotativo(p: calc.Peca):
    """Raio que o rotativo usa (diâmetro no meio da faixa da arte, o mesmo de "Aplicar no rotativo")."""
    return (calc.diametro_em(p, p.inicio) + calc.diametro_em(p, p.inicio + p.altura_arte)) / 4


def uv(pt, p: calc.Peca, arte_w, arte_h, r_ref=None):
    """Coordenadas da arte (0–1 dentro dela) num ponto da malha. O rotativo gira por ÂNGULO: 1 mm em Y da arte =
    sempre o mesmo ângulo (calculado com o raio configurado), em qualquer altura do copo."""
    _, _, _, t, r, z = pt
    return (r_ref or r) * t / arte_w + 0.5, (z - p.inicio) / arte_h


class Vista3D(QWidget):
    arteMovida = Signal(float, float)  # ângulo (graus), início (mm abaixo da boca)
    arteSolta = Signal()               # terminou de arrastar a arte (botão direito/Shift)
    arteAjustada = Signal(float, float)  # setas do teclado: ângulo, início (ajuste dos campos, não é arrasto)

    def __init__(self):
        super().__init__()
        self.p = calc.Peca()
        self.angulo_arte = 0.0
        self.arte = None  # (QImage, largura_mm, altura_mm)
        self.material = next(iter(MATERIAIS))
        self.cor_corpo, self.cor_arte = MATERIAIS[self.material][:2]
        self.yaw, self.pitch, self.zoom = 0.0, 22.0, 1.0
        self._arrasto, self._modo = None, None
        self._tex_cache = None
        self.setMinimumSize(380, 380)
        self.setMouseTracking(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setToolTip("Botão esquerdo: girar a vista · Botão direito (ou Shift): mover a arte · Roda: zoom · "
                        "↑↓ sobe/desce a arte, ←→ gira a arte (Shift = passo maior)")

    # ---------- dados ----------
    def definir(self, p=None, angulo_arte=None, arte=False, material=None, cores=None):
        if p is not None:
            self.p = p
        if angulo_arte is not None:
            self.angulo_arte = angulo_arte
        if arte is not False:
            self.arte = arte
            self._tex_cache = None
        if material is not None and material != self.material:
            self.material = material
            self._tex_cache = None
        if cores is not None and tuple(cores) != (self.cor_corpo, self.cor_arte):
            self.cor_corpo, self.cor_arte = cores
            self._tex_cache = None
        self.update()

    def _textura(self):
        """Arte recolorida com a cor de gravação do material."""
        if self.arte is None:
            return None
        if self._tex_cache is None:
            img = self.arte[0]
            alfa = img.convertToFormat(QImage.Format_Alpha8)
            t = QImage(img.size(), QImage.Format_ARGB32_Premultiplied)
            t.fill(QColor(self.cor_arte))
            t.setAlphaChannel(alfa)
            self._tex_cache = t
        return self._tex_cache

    # ---------- projeção ----------
    def _camera(self):
        cy, sy = math.cos(math.radians(self.yaw)), math.sin(math.radians(self.yaw))
        cp, sp = math.cos(math.radians(self.pitch)), math.sin(math.radians(self.pitch))
        alto = self.p.altura
        tam = max(self.p.altura, calc.diametro_max(self.p))
        dist = tam * 1.9 / self.zoom
        foco = min(self.width(), self.height()) * 1.15
        cx, cyy = self.width() / 2, self.height() / 2

        def proj(x, y, z):
            z = z + alto / 2  # centro da peça na origem
            x1, y1 = x * cy - y * sy, x * sy + y * cy        # gira em volta do eixo vertical
            y2, z2 = y1 * cp - z * sp, y1 * sp + z * cp       # inclina (olhando de cima)
            prof = dist + y2
            k = foco / max(prof, 1e-3)
            return QPointF(cx + x1 * k, cyy - z2 * k), prof

        def visivel_normal(x, y, z, nx, ny, nz):
            z = z + alto / 2
            x1, y1 = x * cy - y * sy, x * sy + y * cy
            y2 = y1 * cp - z * sp
            nx1, ny1 = nx * cy - ny * sy, nx * sy + ny * cy
            ny2, nz2 = ny1 * cp - nz * sp, ny1 * sp + nz * cp
            # câmera em (0, -dist, 0) no espaço girado: vetor do ponto até a câmera
            vx, vy, vz = -x1, -dist - y2, -(z * cp + y1 * sp)
            return nx1 * vx + ny2 * vy + nz2 * vz > 0, (nx1, ny2, nz2)
        return proj, visivel_normal

    # ---------- desenho ----------
    def paintEvent(self, ev):
        pt = QPainter(self)
        pt.setRenderHint(QPainter.Antialiasing)
        fundo = QColor("#30343b")
        pt.fillRect(self.rect(), fundo)
        p = self.p
        if calc.erros(p):
            pt.setPen(QColor("#e8e8e8"))
            pt.drawText(self.rect(), Qt.AlignCenter, "Medidas inválidas")
            return
        proj, vis = self._camera()
        lins = malha(p, self.angulo_arte)
        brilho = MATERIAIS[self.material][2]
        corpo = QColor(self.cor_corpo)
        tex = self._textura()
        arte_w, arte_h = (self.arte[1], self.arte[2]) if self.arte else (1, 1)
        r_ref = raio_rotativo(p)
        luz = (-0.45, -0.75, 0.5)  # em relação à CÂMERA (acima, à esquerda, de frente): gira junto com a vista
        n = math.sqrt(sum(v * v for v in luz))
        luz = tuple(v / n for v in luz)
        faces = []
        for i in range(len(lins) - 1):
            a_lin, b_lin = lins[i], lins[i + 1]
            for j in range(len(a_lin) - 1):
                q = (a_lin[j], a_lin[j + 1], b_lin[j + 1], b_lin[j])
                mx = sum(v[0] for v in q) / 4
                my = sum(v[1] for v in q) / 4
                mz = sum(v[2] for v in q) / 4
                # normal da parede: radial + inclinação da geratriz
                r0, r1 = a_lin[j][4], b_lin[j][4]
                dz = a_lin[j][5] - b_lin[j][5]
                ang = math.atan2(mx, -my)
                inc = math.atan2(r1 - r0, -dz) if dz else 0.0
                nx, ny, nz = math.sin(ang) * math.cos(inc), -math.cos(ang) * math.cos(inc), math.sin(inc)
                pts = [proj(v[0], v[1], v[2]) for v in q]
                frente, nv = vis(mx, my, mz, nx, ny, nz)
                prof = sum(d for _, d in pts) / 4
                faces.append((prof, frente, q, [p2 for p2, _ in pts], nv))
        # fundo (base fechada) e a borda da boca
        base = [proj(v[0], v[1], v[2]) for v in lins[-1]]
        faces.append((sum(d for _, d in base) / len(base), None, None, [p2 for p2, _ in base], (0, 0, -1)))
        faces.sort(key=lambda f: -f[0])  # do mais longe para o mais perto
        for prof, frente, q, poly, nrm in faces:
            pol = QPolygonF(poly)
            if q is None:
                pt.setPen(Qt.NoPen)
                pt.setBrush(corpo.darker(170))
                pt.drawPolygon(pol)
                continue
            if not frente:  # parte de dentro (vista pela boca)
                pt.setPen(Qt.NoPen)
                pt.setBrush(corpo.darker(230))
                pt.drawPolygon(pol)
                continue
            dif = max(0.0, sum(a * b for a, b in zip(nrm, luz)))
            k = 0.35 + 0.65 * dif
            cor = QColor.fromRgbF(min(1, corpo.redF() * k + brilho * dif ** 8 * 0.6),
                                  min(1, corpo.greenF() * k + brilho * dif ** 8 * 0.6),
                                  min(1, corpo.blueF() * k + brilho * dif ** 8 * 0.6))
            pt.setPen(QPen(cor, 0.6))
            pt.setBrush(cor)
            pt.drawPolygon(pol)
            if tex is not None:
                uvs = [uv(v, p, arte_w, arte_h, r_ref) for v in q]
                us, vs = [a for a, _ in uvs], [b for _, b in uvs]
                if max(us) < 0 or min(us) > 1 or max(vs) < 0 or min(vs) > 1:
                    continue
                W, H = tex.width(), tex.height()
                origem = QPolygonF([QPointF(u * W, v * H) for u, v in uvs])
                tf = QTransform()
                if QTransform.quadToQuad(origem, pol, tf):
                    c = pol.boundingRect().center()  # clip um pouco maior: sem frestas entre os pedaços
                    caminho = QPainterPath()
                    caminho.addPolygon(QPolygonF([c + (q2 - c) * 1.08 + (q2 - c) / max(1e-6, (q2 - c).manhattanLength())
                                                  for q2 in poly]))
                    pt.save()
                    pt.setRenderHint(QPainter.Antialiasing, False)
                    pt.setClipPath(caminho)
                    pt.setTransform(tf, True)
                    pt.setOpacity(0.35 + 0.65 * k)
                    pt.drawImage(QPointF(0, 0), tex)
                    pt.restore()
        # boca: elipse da borda
        boca = [proj(v[0], v[1], v[2])[0] for v in lins[0]]
        pt.setPen(QPen(QColor(corpo).lighter(130), 1.6))
        pt.setBrush(Qt.NoBrush)
        pt.drawPolyline(QPolygonF(boca))
        pt.setPen(QColor("#cfd5de"))
        pt.drawText(QRectF(8, 6, self.width() - 16, 18), Qt.AlignLeft,
                    "Esquerdo: girar · Direito/Shift: mover a arte · Roda: zoom")
        if self.arte is None:
            pt.drawText(QRectF(8, self.height() - 24, self.width() - 16, 18), Qt.AlignLeft,
                        "Sem arte: clique em \"Usar a arte do projeto\".")
        pt.end()

    # ---------- mouse ----------
    def mousePressEvent(self, e):
        self.setFocus()
        self._arrasto = e.position()
        mover = e.button() == Qt.RightButton or e.modifiers() & Qt.ShiftModifier
        self._modo = "arte" if mover and self.arte else "girar"

    def mouseMoveEvent(self, e):
        if self._arrasto is None:
            return
        d = e.position() - self._arrasto
        self._arrasto = e.position()
        if self._modo == "girar":
            self.yaw = (self.yaw + d.x() * 0.5) % 360      # arrastar para a direita gira o copo para a direita
            self.pitch = min(80.0, max(-30.0, self.pitch + d.y() * 0.4))  # arrastar para baixo mostra a boca
        else:
            self.angulo_arte = (self.angulo_arte + d.x() * 0.5) % 360  # a arte acompanha o mouse
            mm_px = self.p.altura * 1.3 / max(self.height(), 1) / self.zoom
            novo = min(max(0.0, self.p.inicio + d.y() * mm_px), max(0.0, self.p.altura - self.p.altura_arte))
            self.p = dataclasses.replace(self.p, inicio=novo)
            self.arteMovida.emit(self.angulo_arte, self.p.inicio)
        self.update()

    def mouseReleaseEvent(self, e):
        if self._modo == "arte" and self._arrasto is not None:
            self._arrasto = None
            self.arteSolta.emit()
        self._arrasto = None

    def keyPressEvent(self, e):
        """Setas: ↑↓ sobem/descem a arte (1 mm; Shift 10 mm), ←→ giram a arte (5°; Shift 15°)."""
        grande = bool(e.modifiers() & Qt.ShiftModifier)
        if e.key() in (Qt.Key_Up, Qt.Key_Down):
            passo = (10.0 if grande else 1.0) * (-1 if e.key() == Qt.Key_Up else 1)
            novo = min(max(0.0, self.p.inicio + passo), max(0.0, self.p.altura - self.p.altura_arte))
            self.p = dataclasses.replace(self.p, inicio=novo)
        elif e.key() in (Qt.Key_Left, Qt.Key_Right):
            self.angulo_arte = (self.angulo_arte + (15.0 if grande else 5.0) * (1 if e.key() == Qt.Key_Right else -1)) % 360
        else:
            return super().keyPressEvent(e)
        self.arteAjustada.emit(self.angulo_arte, self.p.inicio)
        self.update()

    def wheelEvent(self, e):
        self.zoom = min(4.0, max(0.4, self.zoom * (1.1 if e.angleDelta().y() > 0 else 1 / 1.1)))
        self.update()
