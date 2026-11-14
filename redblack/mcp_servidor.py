"""Servidor MCP do RedBlack Laser: deixa assistentes (Claude, Codex…) criar e editar projetos .rbl e gerar G-code.

Protocolo MCP por stdio (JSON-RPC 2.0, uma mensagem JSON por linha), sem dependências além do próprio RedBlack.
Trabalha direto nos arquivos de projeto, sem abrir janela; `abrir_no_redblack` abre o projeto no programa.
Nada é enviado à máquina: o G-code é só gravado em arquivo.

Coordenadas: mm, origem no canto SUPERIOR esquerdo da mesa, X para a direita e Y para BAIXO (as mesmas do
arquivo). Executar: python -m redblack.mcp_servidor
"""
import json
import os
import subprocess
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))

from PySide6.QtCore import QPointF, QRectF, QSettings  # noqa: E402
from PySide6.QtGui import QGuiApplication, QPainterPath, QTransform  # noqa: E402

from . import __version__  # noqa: E402
from . import camadas as cm  # noqa: E402
from . import dxf  # noqa: E402
from . import formas as fm  # noqa: E402
from . import gcode as gc  # noqa: E402
from . import geometria as g  # noqa: E402
from . import importar_imagem as imgimp  # noqa: E402
from . import importar_pdf as pdfimp  # noqa: E402
from . import importar_svg as svg  # noqa: E402
from . import objetos as ob  # noqa: E402
from . import percurso as pc  # noqa: E402
from . import projeto as pj  # noqa: E402
from . import texto as tx  # noqa: E402

PROTOCOLO = "2025-06-18"


class ErroFerramenta(Exception):
    """Erro explicado ao assistente (vira resultado com isError)."""


# ---------- projeto em arquivo ----------
def _abrir(arquivo):
    if not arquivo or not str(arquivo).lower().endswith(pj.EXT):
        raise ErroFerramenta(f"Informe o caminho de um projeto {pj.EXT}.")
    if not os.path.exists(arquivo):
        raise ErroFerramenta(f"Projeto não encontrado: {arquivo}")
    try:
        objs, layers, vars_, gab, anc, bloq, notas, (pags, atual, nomes) = pj.load_full(arquivo)
    except pj.ProjetoInvalido as e:
        raise ErroFerramenta(f"Projeto inválido: {e}") from e
    pags = list(pags)
    pags[atual] = (tuple(objs), tuple(anc), tuple(bloq))
    return {"layers": list(layers), "vars": vars_, "gab": gab, "notas": notas, "pags": pags, "atual": atual,
            "nomes": list(nomes)}


def _salvar(arquivo, d):
    atual = d["atual"]
    snaps, anc, bloq = d["pags"][atual]
    lista = [None if i == atual else p for i, p in enumerate(d["pags"])]
    usadas = set().union(*(ob.leaf_layers(s) for p in d["pags"] for s in p[0])) if d["pags"] else set()
    ids = {c.id for c in d["layers"]}
    for lid in sorted(usadas - ids):  # camada usada sem parâmetros: cria com os padrões
        if lid in cm.IDS:
            d["layers"].append(cm.nova(lid, imagem=lid == "C00"))
    pj.save(arquivo, snaps, d["layers"], d["vars"], d["gab"], anc, bloq, d["notas"], lista, atual, d["nomes"])


def _indice_pagina(d, pagina):
    if pagina is None:
        return d["atual"]
    if isinstance(pagina, str) and pagina in d["nomes"]:
        return d["nomes"].index(pagina)
    try:
        i = int(pagina) - 1  # 1 = primeira aba
    except (TypeError, ValueError):
        raise ErroFerramenta(f"Página '{pagina}' não existe. Abas: {d['nomes']}") from None
    if not 0 <= i < len(d["pags"]):
        raise ErroFerramenta(f"Página {pagina} fora de 1 a {len(d['pags'])}.")
    return i


def _caixa(snap):
    r = snap[1].map(snap[0]).boundingRect()
    return {"x": round(r.x(), 3), "y": round(r.y(), 3), "largura": round(r.width(), 3), "altura": round(r.height(), 3)}


def _tipo(snap):
    e = snap[5]
    return ("grupo" if isinstance(e, ob.GroupData) else "texto" if isinstance(e, tx.TextoParams)
            else "imagem" if isinstance(e, imgimp.ImagemOriginal) else "vetor")


def _camada(c):
    return {k: getattr(c, k) for k in ("id", "nome", "modo", "velocidade_mm_min", "potencia_max", "potencia_min",
                                       "passadas", "intervalo_mm", "saida", "air")} | {"subcamadas": len(c.subcamadas)}


def _carregar_maquina():
    s = QSettings("RedBlack", "RedBlackLaser")
    try:
        v = json.loads(s.value("maquina", "") or "{}")
        g.definir_mesa(v.get("largura", 365.0), v.get("altura", 370.0), v.get("origem", "inf_esq"))
        gc.definir_perfil(v.get("comando", "M3"), int(v.get("s_max", 1000)), v.get("f_max", 20000.0))
    except (TypeError, ValueError):
        g.definir_mesa(365.0, 370.0, "inf_esq")
        gc.definir_perfil()


# ---------- ferramentas ----------
def projeto_info(arquivo):
    d = _abrir(arquivo)
    return {"arquivo": arquivo, "mesa_mm": [g.BED_W, g.BED_H], "origem_maquina": g.CANTOS[g.ORIGEM],
            "pagina_aberta": d["atual"] + 1,
            "paginas": [{"numero": i + 1, "nome": n, "objetos": len(p[0])} for i, (n, p) in enumerate(zip(d["nomes"],
                                                                                                         d["pags"]))],
            "camadas": [_camada(c) for c in d["layers"]], "notas": d["notas"][:2000]}


def listar_objetos(arquivo, pagina=None):
    d = _abrir(arquivo)
    i = _indice_pagina(d, pagina)
    return {"pagina": d["nomes"][i], "objetos": [
        {"nome": s[2], "tipo": _tipo(s), "camadas": sorted(ob.leaf_layers(s)), **_caixa(s)} for s in d["pags"][i][0]]}


def criar_projeto(arquivo, paginas=None, sobrescrever=False):
    if not str(arquivo).lower().endswith(pj.EXT):
        raise ErroFerramenta(f"O arquivo precisa terminar em {pj.EXT}.")
    if os.path.exists(arquivo) and not sobrescrever:
        raise ErroFerramenta("O arquivo já existe. Use sobrescrever=true para substituir.")
    nomes = [str(n).strip()[:pj.MAX_NOME_PAGINA] for n in (paginas or ["Página 1"]) if str(n).strip()] or ["Página 1"]
    os.makedirs(os.path.dirname(os.path.abspath(arquivo)), exist_ok=True)
    d = {"layers": [cm.nova("C01")], "vars": None, "gab": None, "notas": "", "pags": [((), (), ()) for _ in nomes],
         "atual": 0, "nomes": nomes}
    _salvar(arquivo, d)
    return {"criado": arquivo, "paginas": nomes}


def _forma(tipo, a):
    """QPainterPath (mm, Y para baixo) e, para texto, os parâmetros."""
    x, y = float(a.get("x", 0)), float(a.get("y", 0))
    w, h = float(a.get("largura", 0)), float(a.get("altura", 0))
    if tipo in ("retangulo", "elipse"):
        if w <= 0 or h <= 0:
            raise ErroFerramenta("largura e altura devem ser positivas.")
        r = QRectF(x, y, w, h)
        if tipo == "elipse":
            return fm.ellipse_path(r), None
        p = fm.rect_path(r)
        return (fm.arredondar(p, float(a.get("raio_canto", 0)))[0] if a.get("raio_canto") else p), None
    if tipo == "circulo":
        d = float(a.get("diametro", 0))
        if d <= 0:
            raise ErroFerramenta("diametro deve ser positivo (x, y = centro).")
        return fm.ellipse_path(QRectF(x - d / 2, y - d / 2, d, d)), None
    if tipo in ("poligono", "estrela"):
        r, n = float(a.get("raio", 0)), int(a.get("lados", 6))
        if r <= 0 or n < 3:
            raise ErroFerramenta("raio > 0 e lados >= 3 (x, y = centro).")
        c = QPointF(x, y)
        return (fm.star_path(c, r, n, float(a.get("razao", 0.5))) if tipo == "estrela" else fm.polygon_path(c, r, n)), None
    if tipo == "linha":
        pts = a.get("pontos") or []
        if len(pts) < 2:
            raise ErroFerramenta("linha precisa de 'pontos': [[x, y], ...] com 2 ou mais pontos.")
        return fm.polyline_path([QPointF(float(p[0]), float(p[1])) for p in pts], bool(a.get("fechado"))), None
    if tipo == "caminho_svg":
        try:
            p = svg.parse_path(str(a.get("d", "")))
        except Exception as e:
            raise ErroFerramenta(f"Caminho SVG inválido: {e}") from e
        if p.isEmpty():
            raise ErroFerramenta("Caminho SVG vazio (use o atributo d: 'M 0 0 C ... Z').")
        return QTransform.fromTranslate(x, y).map(p), None
    if tipo == "texto":
        t = str(a.get("texto", ""))
        if not t:
            raise ErroFerramenta("Informe 'texto'.")
        fonte = a.get("fonte") or ("Arial" if tx.font_available("Arial") else QGuiApplication.font().family())
        if not tx.font_available(fonte):
            raise ErroFerramenta(f"Fonte não instalada: {fonte}")
        prm = tx.TextoParams(t, fonte, float(a.get("altura_texto", 10)), bool(a.get("negrito")),
                             bool(a.get("italico")), a.get("alinhamento", "esquerda"))
        return tx.build_path(prm), prm  # posição pela matriz (x, y = início da linha de base)
    raise ErroFerramenta(f"Tipo de forma desconhecido: {tipo}")


def adicionar_forma(arquivo, tipo, pagina=None, camada="C01", nome=None, **args):
    if camada not in cm.IDS:
        raise ErroFerramenta(f"Camada inválida: {camada} (use C00 a C{len(cm.IDS) - 1:02d}).")
    d = _abrir(arquivo)
    i = _indice_pagina(d, pagina)
    path, prm = _forma(tipo, args)
    tf = QTransform.fromTranslate(float(args.get("x", 0)), float(args.get("y", 0))) if prm else QTransform()
    nome = nome or f"{tipo.capitalize()} {len(d['pags'][i][0]) + 1}"
    snap = (path, tf, nome, camada, cm.cor(camada), prm)
    snaps, anc, bloq = d["pags"][i]
    d["pags"][i] = (tuple(snaps) + (snap,), anc, bloq)
    _salvar(arquivo, d)
    return {"adicionado": nome, "pagina": d["nomes"][i], "camada": camada, **_caixa(snap)}


def importar_arquivo(arquivo, caminho, pagina=None, camada="C01", x=None, y=None):
    d = _abrir(arquivo)
    i = _indice_pagina(d, pagina)
    ext = os.path.splitext(caminho)[1].lower()
    if not os.path.exists(caminho):
        raise ErroFerramenta(f"Arquivo não encontrado: {caminho}")
    novos, avisos = [], []
    try:
        if ext in (".png", ".jpg", ".jpeg"):
            res = imgimp.load(caminho)
            r = QPainterPath()
            r.addRect(QRectF(0, 0, res.largura_mm, res.altura_mm))
            novos = [(r, QTransform(), os.path.basename(caminho), "C00", cm.cor("C00"), res.imagem)]
        else:
            res = (pdfimp.load(caminho) if ext in (".pdf", ".ai") else svg.load(caminho) if ext == ".svg"
                   else dxf.load(caminho, g.BED_H) if ext == ".dxf" else None)
            if res is None:
                raise ErroFerramenta("Formatos aceitos: SVG, DXF, PDF, AI, PNG, JPG.")
            novos = [(p, QTransform(), n, camada, cm.cor(camada), None) for n, p in res.objetos]
            avisos = list(res.avisos) + [f"{k}: {v} ignorado(s)" for k, v in res.ignorados.items()]
    except (svg.SvgInvalido, dxf.DxfInvalido, pdfimp.PdfInvalido, imgimp.ImagemInvalida, OSError) as e:
        raise ErroFerramenta(f"Não foi possível importar: {e}") from e
    if not novos:
        raise ErroFerramenta("Nada importável no arquivo. " + "; ".join(avisos))
    if x is not None or y is not None:  # canto superior esquerdo do conjunto em (x, y)
        r = QRectF()
        for s in novos:
            r = r.united(s[1].map(s[0]).boundingRect())
        dx = (float(x) - r.left()) if x is not None else 0.0
        dy = (float(y) - r.top()) if y is not None else 0.0
        novos = [(s[0], s[1] * QTransform.fromTranslate(dx, dy), *s[2:]) for s in novos]
    snaps, anc, bloq = d["pags"][i]
    d["pags"][i] = (tuple(snaps) + tuple(novos), anc, bloq)
    _salvar(arquivo, d)
    return {"importados": len(novos), "pagina": d["nomes"][i], "avisos": avisos}


def remover_objetos(arquivo, nomes, pagina=None):
    d = _abrir(arquivo)
    i = _indice_pagina(d, pagina)
    snaps, anc, bloq = d["pags"][i]
    fica = [k for k, s in enumerate(snaps) if s[2] not in set(nomes)]
    if len(fica) == len(snaps):
        raise ErroFerramenta(f"Nenhum objeto com esses nomes em '{d['nomes'][i]}'.")
    novo = {old: new for new, old in enumerate(fica)}
    d["pags"][i] = (tuple(snaps[k] for k in fica), tuple((novo[f], novo[a]) for f, a in anc if f in novo and a in novo),
                    tuple(novo[b] for b in bloq if b in novo))
    _salvar(arquivo, d)
    return {"removidos": len(snaps) - len(fica), "restam": len(fica)}


def configurar_camada(arquivo, camada, campos):
    d = _abrir(arquivo)
    atual = next((c for c in d["layers"] if c.id == camada), None)
    if atual is None:
        if camada not in cm.IDS:
            raise ErroFerramenta(f"Camada inválida: {camada}")
        atual = cm.nova(camada)
        d["layers"].append(atual)
    campos = dict(campos or {})
    if "passadas" in campos:
        campos["passadas"] = int(campos["passadas"])
    validos = set(atual.__dataclass_fields__) - {"id", "subcamadas"}
    errados = set(campos) - validos
    if errados:
        raise ErroFerramenta(f"Campos desconhecidos: {sorted(errados)}. Válidos: {sorted(validos)}")
    try:
        novo = cm.alterar(atual, **campos)
    except ValueError as e:
        raise ErroFerramenta(f"Valor recusado: {e}") from e
    d["layers"][d["layers"].index(atual)] = novo
    _salvar(arquivo, d)
    return {"camada": _camada(novo)}


def gerenciar_pagina(arquivo, acao, pagina=None, nome=None):
    d = _abrir(arquivo)
    if acao == "adicionar":
        d["pags"].append(((), (), ()))
        d["nomes"].append((nome or f"Página {len(d['pags'])}")[:pj.MAX_NOME_PAGINA])
    else:
        i = _indice_pagina(d, pagina)
        if acao == "renomear":
            if not (nome or "").strip():
                raise ErroFerramenta("Informe o novo nome.")
            d["nomes"][i] = nome.strip()[:pj.MAX_NOME_PAGINA]
        elif acao == "duplicar":
            d["pags"].insert(i + 1, d["pags"][i])
            d["nomes"].insert(i + 1, (nome or d["nomes"][i] + " (cópia)")[:pj.MAX_NOME_PAGINA])
            if d["atual"] > i:
                d["atual"] += 1
        elif acao == "excluir":
            if len(d["pags"]) < 2:
                raise ErroFerramenta("O projeto precisa de pelo menos uma página.")
            del d["pags"][i], d["nomes"][i]
            if d["atual"] > i:  # a aba aberta continua a mesma
                d["atual"] -= 1
            d["atual"] = min(d["atual"], len(d["pags"]) - 1)  # se a apagada era a aberta: a vizinha
        else:
            raise ErroFerramenta("acao: adicionar, renomear, duplicar ou excluir.")
    if len(d["pags"]) > pj.MAX_PAGINAS:
        raise ErroFerramenta(f"Limite de {pj.MAX_PAGINAS} páginas.")
    _salvar(arquivo, d)
    return {"paginas": d["nomes"]}


def gerar_gcode(arquivo, destino, pagina=None, sobrescrever=False):
    d = _abrir(arquivo)
    i = _indice_pagina(d, pagina)
    if os.path.exists(destino) and not sobrescrever:
        raise ErroFerramenta("O G-code de destino já existe. Use sobrescrever=true.")
    _carregar_maquina()
    snaps = d["pags"][i][0]
    try:
        perc = pc.gerar(list(snaps), d["layers"])
        texto = gc.gerar(perc, d["layers"])
    except (gc.GcodeInvalido, pc.LimiteExcedido) as e:
        raise ErroFerramenta(f"G-code não gerado: {e}") from e
    info = gc.analisar(texto)
    if not (info["dentro_da_area"] and info["fim_desligado"]):
        raise ErroFerramenta("Conferência do G-code falhou (área ou laser ao final).")
    gc.salvar(destino, texto)
    return {"gcode": destino, "pagina": d["nomes"][i], "linhas": texto.count("\n"),
            "tempo_estimado": pc.fmt_tempo(perc.tempo_s), "mm_com_laser": round(info["comprimento_corte"], 1),
            "area_x_mm": info["x"], "area_y_mm": info["y"],
            "aviso": "Nada foi enviado à máquina. Valores de máquina e material não validados: confira antes."}


def _exe_redblack():
    cand = [os.environ.get("REDBLACK_EXE", "")]
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")):
        cand += [os.path.join(base, "Programs", "RedBlack Laser", "RedBlackLaser.exe"),
                 os.path.join(base, "RedBlack Laser", "RedBlackLaser.exe")]
    return next((c for c in cand if c and os.path.exists(c)), None)


def abrir_no_redblack(arquivo):
    if not os.path.exists(arquivo):
        raise ErroFerramenta(f"Projeto não encontrado: {arquivo}")
    exe = _exe_redblack()
    cmd = [exe, arquivo] if exe else [sys.executable.replace("python.exe", "pythonw.exe"), "-m", "redblack", arquivo]
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(cmd, cwd=raiz, creationflags=flags, close_fds=True)
    return {"aberto": arquivo, "programa": cmd[0]}


# ---------- descrição das ferramentas ----------
ARQ = {"type": "string", "description": "Caminho completo do projeto .rbl"}
PAG = {"type": ["integer", "string"], "description": "Número da aba (1 = primeira) ou nome; padrão: a aba aberta"}
CAM = {"type": "string", "description": "Camada C00 a C29 (C00 = imagens; C01 azul, C02 vermelha…)", "default": "C01"}

FERRAMENTAS = {
    "projeto_info": (projeto_info, "Resumo do projeto RedBlack: abas (páginas), camadas com parâmetros, mesa e notas.",
                     {"arquivo": ARQ}, ["arquivo"]),
    "listar_objetos": (listar_objetos, "Objetos de uma aba com tipo, camadas e caixa (x, y = canto superior esquerdo, "
                       "mm, Y para baixo).", {"arquivo": ARQ, "pagina": PAG}, ["arquivo"]),
    "criar_projeto": (criar_projeto, "Cria um projeto .rbl vazio com abas nomeadas.",
                      {"arquivo": ARQ, "paginas": {"type": "array", "items": {"type": "string"},
                                                   "description": "Nomes das abas, ex.: ['Parte 1', 'Parte 2']"},
                       "sobrescrever": {"type": "boolean", "default": False}}, ["arquivo"]),
    "adicionar_forma": (adicionar_forma, "Adiciona uma forma em mm (origem no canto superior esquerdo da mesa, Y para "
                        "baixo). retangulo/elipse: x, y, largura, altura (+ raio_canto); circulo: x, y = centro, "
                        "diametro; poligono/estrela: x, y = centro, raio, lados (+ razao); linha: pontos [[x,y],...], "
                        "fechado; caminho_svg: d (sintaxe SVG, em mm) deslocado por x, y; texto: texto, x, y (linha de "
                        "base), altura_texto (altura do X), fonte, negrito, italico.",
                        {"arquivo": ARQ, "pagina": PAG, "camada": CAM, "nome": {"type": "string"},
                         "tipo": {"type": "string", "enum": ["retangulo", "elipse", "circulo", "poligono", "estrela",
                                                             "linha", "caminho_svg", "texto"]},
                         "x": {"type": "number"}, "y": {"type": "number"}, "largura": {"type": "number"},
                         "altura": {"type": "number"}, "raio_canto": {"type": "number"}, "diametro": {"type": "number"},
                         "raio": {"type": "number"}, "lados": {"type": "integer"}, "razao": {"type": "number"},
                         "pontos": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
                         "fechado": {"type": "boolean"}, "d": {"type": "string"}, "texto": {"type": "string"},
                         "altura_texto": {"type": "number"}, "fonte": {"type": "string"},
                         "negrito": {"type": "boolean"}, "italico": {"type": "boolean"},
                         "alinhamento": {"type": "string", "enum": ["esquerda", "centro", "direita"]}},
                        ["arquivo", "tipo"]),
    "importar_arquivo": (importar_arquivo, "Importa SVG, DXF, PDF, AI (vetores) ou PNG/JPG (imagem) para uma aba; "
                         "x, y opcionais = canto superior esquerdo do que entrar.",
                         {"arquivo": ARQ, "caminho": {"type": "string"}, "pagina": PAG, "camada": CAM,
                          "x": {"type": "number"}, "y": {"type": "number"}}, ["arquivo", "caminho"]),
    "remover_objetos": (remover_objetos, "Remove objetos de uma aba pelo nome.",
                        {"arquivo": ARQ, "pagina": PAG, "nomes": {"type": "array", "items": {"type": "string"}}},
                        ["arquivo", "nomes"]),
    "configurar_camada": (configurar_camada, "Altera parâmetros de uma camada (cria se não existir). campos, ex.: "
                          "{\"nome\": \"Corte\", \"modo\": \"linha\", \"velocidade_mm_min\": 300, \"potencia_max\": "
                          "100, \"passadas\": 2, \"intervalo_mm\": 0.1, \"saida\": true, \"air\": true, \"kerf_mm\": 0}. "
                          "modo: linha, preenchimento ou imagem.",
                          {"arquivo": ARQ, "camada": CAM, "campos": {"type": "object"}}, ["arquivo", "camada", "campos"]),
    "gerenciar_pagina": (gerenciar_pagina, "Abas do projeto: adicionar (nome), renomear (pagina, nome), duplicar "
                         "(pagina) ou excluir (pagina).",
                         {"arquivo": ARQ, "acao": {"type": "string", "enum": ["adicionar", "renomear", "duplicar",
                                                                              "excluir"]},
                          "pagina": PAG, "nome": {"type": "string"}}, ["arquivo", "acao"]),
    "gerar_gcode": (gerar_gcode, "Gera o G-code GRBL de uma aba num arquivo (usa as Configurações da máquina do "
                    "RedBlack) e devolve tempo estimado e área. NÃO envia nada à máquina.",
                    {"arquivo": ARQ, "destino": {"type": "string", "description": "Caminho do .gcode"},
                     "pagina": PAG, "sobrescrever": {"type": "boolean", "default": False}}, ["arquivo", "destino"]),
    "abrir_no_redblack": (abrir_no_redblack, "Abre o projeto na janela do RedBlack Laser.", {"arquivo": ARQ},
                          ["arquivo"]),
}


def _lista_ferramentas():
    return [{"name": n, "description": desc, "inputSchema": {"type": "object", "properties": props, "required": req}}
            for n, (_, desc, props, req) in FERRAMENTAS.items()]


def tratar(msg):
    """Uma mensagem JSON-RPC -> resposta (ou None para notificações)."""
    mid, metodo, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None  # notificação (ex.: notifications/initialized)

    def ok(res):
        return {"jsonrpc": "2.0", "id": mid, "result": res}
    if metodo == "initialize":
        return ok({"protocolVersion": params.get("protocolVersion") or PROTOCOLO,
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "redblack-laser", "version": __version__},
                   "instructions": "RedBlack Laser: crie e edite projetos de corte/gravação a laser (.rbl) e gere "
                                   "G-code. Medidas em mm; origem no canto superior esquerdo da mesa, Y para baixo. "
                                   "Furos em camada cortada antes do contorno (ex.: C02 antes de C01)."})
    if metodo == "ping":
        return ok({})
    if metodo == "tools/list":
        return ok({"tools": _lista_ferramentas()})
    if metodo == "tools/call":
        nome, args = params.get("name"), params.get("arguments") or {}
        if nome not in FERRAMENTAS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Ferramenta desconhecida: {nome}"}}
        try:
            res = FERRAMENTAS[nome][0](**args)
            return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=1)}],
                       "isError": False})
        except ErroFerramenta as e:
            return ok({"content": [{"type": "text", "text": str(e)}], "isError": True})
        except TypeError as e:  # argumento faltando/sobrando
            return ok({"content": [{"type": "text", "text": f"Argumentos inválidos: {e}"}], "isError": True})
        except Exception as e:  # erro interno: devolve explicado em vez de derrubar o servidor
            traceback.print_exc(file=sys.stderr)
            return ok({"content": [{"type": "text", "text": f"Erro interno: {type(e).__name__}: {e}"}], "isError": True})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Método não suportado: {metodo}"}}


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841  (fontes e caminhos do Qt)
    entrada = open(sys.stdin.fileno(), "r", encoding="utf-8", closefd=False)
    saida = open(sys.stdout.fileno(), "w", encoding="utf-8", closefd=False, newline="\n")
    for linha in entrada:
        linha = linha.strip()
        if not linha:
            continue
        try:
            msg = json.loads(linha)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido"}}
        else:
            resp = tratar(msg) if isinstance(msg, dict) else None
        if resp is not None:
            saida.write(json.dumps(resp, ensure_ascii=False) + "\n")
            saida.flush()


if __name__ == "__main__":
    main()
