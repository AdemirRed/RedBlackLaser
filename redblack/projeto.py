"""Formato de projeto próprio (.rbl): JSON versionado, unidades em mm.

Cada objeto guarda o caminho original (comandos M/L/C em coordenadas locais) e a matriz
3×3 completa, portanto a geometria é recuperada sem perda (floats em JSON fazem ida e volta exata).
"""
import base64
import binascii
import dataclasses
import hashlib
import json
import math
import os
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainterPath, QTransform

from . import __version__
from . import camadas as cm
from . import gabarito as gbm
from . import importar_imagem as im
from . import objetos as ob
from . import texto as tx
from . import variaveis as vr

FORMAT = "redblack-laser"
# 2: imagem (original embutido). 3: texto editável. 4: grupos. 5: camadas com parâmetros.
# 6: texto variável (planilha embutida). 7: gabarito na mesa e peça do texto variável. 8: kerf por camada. 9: âncoras. 10: objetos bloqueados. 11–14: varredura, guias, sobrecorte, preencher juntas e
# gravação de imagem (modo, limiar, negativo) (ângulo, bidirecional, hachura cruzada,
# sobrevarredura).
# Versões anteriores continuam legíveis.
VERSION = 18  # 18: páginas; 17: texto com maiúsculas/soldado/distorcer; camada com meio-tom (cpi, ângulo) entrada/saída do corte e subcamadas
MAX_DEPTH = 32  # grupos dentro de grupos; protege contra arquivos maliciosos
EXT = ".rbl"
MAX_BYTES = 200 * 1024 * 1024  # proteção contra arquivos absurdos
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_ARGS = {"M": 2, "L": 2, "C": 6}


class ProjetoInvalido(Exception):
    """Arquivo não é um projeto válido; a mensagem é exibida ao usuário."""


# ---------- caminhos ----------
def path_to_list(p: QPainterPath) -> list:
    out, i, n = [], 0, p.elementCount()
    while i < n:
        e = p.elementAt(i)
        if e.type == QPainterPath.MoveToElement:
            out.append(["M", e.x, e.y])
        elif e.type == QPainterPath.LineToElement:
            out.append(["L", e.x, e.y])
        elif e.type == QPainterPath.CurveToElement:
            c2, end = p.elementAt(i + 1), p.elementAt(i + 2)
            out.append(["C", e.x, e.y, c2.x, c2.y, end.x, end.y])
            i += 2
        i += 1
    return out


def list_to_path(cmds: list, winding: bool) -> QPainterPath:
    p = QPainterPath()
    p.setFillRule(Qt.WindingFill if winding else Qt.OddEvenFill)
    for c in cmds:
        if c[0] == "M":
            p.moveTo(c[1], c[2])
        elif c[0] == "L":
            p.lineTo(c[1], c[2])
        else:
            p.cubicTo(*c[1:])
    return p


# ---------- documento ----------
def _obj_to_dict(snap) -> dict:
    path, tf, name, layer, color, extra = snap
    imagem = extra if isinstance(extra, im.ImagemOriginal) else None
    texto = extra if isinstance(extra, tx.TextoParams) else None
    grupo = extra if isinstance(extra, ob.GroupData) else None
    o = {
        "tipo": "imagem" if imagem else "texto" if texto else "grupo" if grupo else "vetor",
        "nome": name, "camada": layer, "cor": color,
        "matriz": [tf.m11(), tf.m12(), tf.m13(), tf.m21(), tf.m22(), tf.m23(), tf.m31(), tf.m32(), tf.m33()],
        "preenchimento": "winding" if path.fillRule() == Qt.WindingFill else "oddeven",
        "caminho": path_to_list(path),
    }
    if imagem:
        # Original embutido byte a byte: o projeto não depende do arquivo de origem.
        o["imagem"] = {"formato": imagem.formato, "arquivo": imagem.arquivo, "sha256": imagem.sha256,
                       "dados": base64.b64encode(imagem.dados).decode("ascii")}
    if texto:
        # O "caminho" acima guarda o contorno: o projeto abre igual mesmo sem a fonte instalada.
        o["texto"] = dataclasses.asdict(texto)
    if grupo:
        o["filhos"] = [_obj_to_dict(c) for c in grupo.children]  # matrizes relativas ao grupo
    return o


MAX_PAGINAS = 100


def _pagina_to_dict(pagina) -> dict:
    snaps, ancoras, bloqueados = pagina
    d = {"objetos": [_obj_to_dict(s) for s in snaps]}
    if ancoras:
        d["ancoras"] = [[f, a] for f, a in ancoras]
    if bloqueados:
        d["bloqueados"] = sorted(bloqueados)
    return d


def to_dict(snapshots, camadas=(), variaveis=None, gabarito=None, ancoras=(), bloqueados=(), notas="",
            paginas=(None,), pagina_atual=0, nomes_paginas=None) -> dict:
    """paginas: uma entrada por página, na ordem; a da página aberta é None (ela vem em snapshots/ancoras/
    bloqueados, no topo do arquivo); as outras são (snapshots, ancoras, bloqueados)."""
    d = {"formato": FORMAT, "versao": VERSION, "criado_por": f"RedBlack Laser {__version__}",
         "unidade": "mm", "camadas": [dataclasses.asdict(c) for c in camadas],  # ordem = ordem de saída
         "objetos": [_obj_to_dict(s) for s in snapshots]}
    if variaveis is not None and variaveis != vr.DadosVariaveis():
        v = dataclasses.asdict(variaveis)
        v["colunas"], v["linhas"] = list(variaveis.colunas), [list(ln) for ln in variaveis.linhas]
        d["variaveis"] = v  # planilha embutida: o projeto não depende do CSV original
    if gabarito is not None:
        d["gabarito"] = gbm.para_dict(gabarito)
    if ancoras:
        d["ancoras"] = [[f, a] for f, a in ancoras]  # [índice do objeto preso, índice da âncora]
    if bloqueados:
        d["bloqueados"] = sorted(bloqueados)
    if notas:
        d["notas"] = notas
    nomes = list(nomes_paginas or nomes_padrao(len(paginas)))
    if len(paginas) > 1 or nomes != nomes_padrao(len(paginas)):
        d["paginas"] = [None if p is None else _pagina_to_dict(p) for p in paginas]
        d["pagina_atual"] = pagina_atual
        d["nomes_paginas"] = nomes
    return d


MAX_NOME_PAGINA = 60


def nomes_padrao(n) -> list:
    return [f"Página {i}" for i in range(1, n + 1)]


def paginas_from_dict(d) -> tuple:
    """(lista de páginas com None na aberta, índice da aberta, nomes). Sem páginas: ([None], 0, ["Página 1"])."""
    raw = d.get("paginas")
    if raw is None:
        return [None], 0, nomes_padrao(1)
    atual = d.get("pagina_atual")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_PAGINAS or isinstance(atual, bool) \
            or not isinstance(atual, int) or not 0 <= atual < len(raw) or raw[atual] is not None \
            or sum(p is None for p in raw) != 1:
        raise ProjetoInvalido("Lista de páginas inválida.")
    out = []
    for k, p in enumerate(raw, 1):
        if p is None:
            out.append(None)
            continue
        if not isinstance(p, dict) or not isinstance(p.get("objetos"), list):
            raise ProjetoInvalido(f"Página {k} inválida.")
        sub = {"formato": FORMAT, "versao": VERSION, "unidade": "mm", "objetos": p["objetos"]}
        try:
            snaps = from_dict(sub)
        except ProjetoInvalido as e:
            raise ProjetoInvalido(f"Página {k}: {e}") from e
        out.append((tuple(snaps), ancoras_from_dict(p, len(snaps)), bloqueados_from_dict(p, len(snaps))))
    nomes = d.get("nomes_paginas", nomes_padrao(len(out)))  # ausente na versão 18 sem nomes
    if not isinstance(nomes, list) or len(nomes) != len(out) or not all(
            isinstance(n, str) and 0 < len(n.strip()) <= MAX_NOME_PAGINA for n in nomes):
        raise ProjetoInvalido("Nomes das páginas inválidos.")
    return out, atual, nomes


MAX_NOTAS = 100_000


def notas_from_dict(d) -> str:
    n = d.get("notas", "")
    if not isinstance(n, str) or len(n) > MAX_NOTAS:
        raise ProjetoInvalido("Notas do projeto inválidas.")
    return n


def bloqueados_from_dict(d, n_objetos) -> tuple:
    raw = d.get("bloqueados", [])
    if not (isinstance(raw, list) and all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < n_objetos
                                          for i in raw) and len(set(raw)) == len(raw)):
        raise ProjetoInvalido("Lista de objetos bloqueados inválida.")
    return tuple(sorted(raw))


def ancoras_from_dict(d, n_objetos) -> tuple:
    """Pares (filho, âncora) por índice de objeto; recusa índices fora, repetidos e ciclos."""
    raw = d.get("ancoras", [])
    if not isinstance(raw, list):
        raise ProjetoInvalido("Lista de âncoras inválida.")
    pai = {}
    for par in raw:
        if not (isinstance(par, list) and len(par) == 2 and all(isinstance(i, int) and not isinstance(i, bool)
                                                                 and 0 <= i < n_objetos for i in par)):
            raise ProjetoInvalido("Âncora com índice inválido.")
        f, a = par
        if f == a or f in pai:
            raise ProjetoInvalido("Âncora repetida ou presa a si mesma.")
        pai[f] = a
    for f in pai:  # sem ciclos: subir pelas âncoras termina
        visto, x = set(), f
        while x in pai:
            if x in visto:
                raise ProjetoInvalido("Âncoras em ciclo.")
            visto.add(x)
            x = pai[x]
    return tuple(sorted(pai.items()))


# Campos de camada que projetos antigos não têm (recebem o padrão ao abrir).
CAMPOS_NOVOS_CAMADA = {"kerf_mm", "angulo_graus", "angulo_inc_graus", "bidirecional", "hachura_cruzada",
                       "sobrevarredura_mm", "guias_qtd", "guias_mm", "sobrecorte_mm", "preencher_juntas", "modo_imagem",
                       "limiar_pct", "negativo", "brilho_pct", "contraste_pct", "gama",
                       "meio_tom_cpi", "meio_tom_angulo", "entrada_mm", "saida_corte_mm",
                       "subcamadas"}


def layers_from_dict(d) -> list:
    """Camadas do projeto (vazia em projetos anteriores à versão 5). Chamar após from_dict(d)."""
    raw = d.get("camadas", [])
    if not isinstance(raw, list):
        raise ProjetoInvalido("Lista de camadas inválida.")
    out, seen = [], set()
    fields = {f.name for f in dataclasses.fields(cm.Camada)}
    for i, c in enumerate(raw, 1):
        if isinstance(c, dict) and set(c) <= fields and fields - set(c) <= CAMPOS_NOVOS_CAMADA:
            padrao = cm.Camada("C01", "")
            c = {**{k: getattr(padrao, k) for k in fields - set(c)}, **c}  # projetos antigos: valores padrão
        if not isinstance(c, dict) or set(c) != fields:
            raise ProjetoInvalido(f"Camada {i} com campos ausentes ou desconhecidos.")
        sub = c.get("subcamadas", ())  # JSON: listas -> tuplas ((campo, valor), …)
        if isinstance(sub, list):
            try:
                c = {**c, "subcamadas": tuple(tuple(tuple(p) for p in s) for s in sub)}
            except TypeError as e:
                raise ProjetoInvalido(f"Subcamadas da camada {i} inválidas.") from e
        try:
            camada = cm.Camada(**c)
        except TypeError as e:
            raise ProjetoInvalido(f"Camada {i} inválida.") from e
        erros = cm.validar(camada)
        if not isinstance(camada.nome, str):
            erros.append("nome deve ser texto")
        if erros:
            raise ProjetoInvalido(f"Camada {i} ({c.get('id')}): " + "; ".join(erros))
        if camada.id in seen:
            raise ProjetoInvalido(f"Camada {camada.id} repetida.")
        seen.add(camada.id)
        out.append(camada)
    return out


def _num(v, where):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ProjetoInvalido(f"Número inválido em {where}.")
    return float(v)


def _str(o, key, where):
    v = o.get(key)
    if not isinstance(v, str):
        raise ProjetoInvalido(f"Campo '{key}' ausente ou inválido em {where}.")
    return v


def from_dict(d) -> list:
    """Valida tudo antes de devolver; nada é aplicado ao documento se algo estiver errado."""
    if not isinstance(d, dict) or d.get("formato") != FORMAT:
        raise ProjetoInvalido("O arquivo não é um projeto do RedBlack Laser.")
    ver = d.get("versao")
    if not isinstance(ver, int) or isinstance(ver, bool) or ver < 1:
        raise ProjetoInvalido("Versão do projeto ausente ou inválida.")
    if ver > VERSION:
        raise ProjetoInvalido(f"Projeto criado por uma versão mais nova (formato {ver}); "
                              f"esta versão lê até o formato {VERSION}.")
    if d.get("unidade") != "mm":
        raise ProjetoInvalido("Unidade do projeto não suportada (esperado: mm).")
    objs = d.get("objetos")
    if not isinstance(objs, list):
        raise ProjetoInvalido("Lista de objetos ausente.")
    return [_parse_obj(o, f"objeto {i}", 0) for i, o in enumerate(objs, 1)]


def _parse_obj(o, where, depth):
    if depth > MAX_DEPTH:
        raise ProjetoInvalido(f"Grupos aninhados demais no {where}.")
    if not isinstance(o, dict):
        raise ProjetoInvalido(f"Formato inválido no {where}.")
    name, layer, color = _str(o, "nome", where), _str(o, "camada", where), _str(o, "cor", where)
    if not _COLOR.match(color):
        raise ProjetoInvalido(f"Cor inválida no {where}.")
    m = o.get("matriz")
    if not isinstance(m, list) or len(m) != 9:
        raise ProjetoInvalido(f"Matriz inválida no {where}.")
    tf = QTransform(*(_num(v, where) for v in m))
    if not tf.isInvertible():
        raise ProjetoInvalido(f"Matriz degenerada no {where}.")
    cmds = o.get("caminho")
    if not isinstance(cmds, list) or not cmds:
        raise ProjetoInvalido(f"Caminho vazio ou inválido no {where}.")
    clean = []
    for c in cmds:
        if not isinstance(c, list) or not c or c[0] not in _ARGS or len(c) != _ARGS[c[0]] + 1:
            raise ProjetoInvalido(f"Comando de caminho inválido no {where}.")
        clean.append([c[0], *(_num(v, where) for v in c[1:])])
    if clean[0][0] != "M":
        raise ProjetoInvalido(f"Caminho deve começar com M no {where}.")
    fill = o.get("preenchimento", "oddeven")
    if fill not in ("winding", "oddeven"):
        raise ProjetoInvalido(f"Preenchimento inválido no {where}.")
    tipo = o.get("tipo", "vetor")  # versão 1 só tinha vetores
    if tipo == "imagem":
        extra = _imagem(o.get("imagem"), where)
    elif tipo == "texto":
        extra = _texto(o.get("texto"), where)
    elif tipo == "grupo":
        filhos = o.get("filhos")
        if not isinstance(filhos, list) or not filhos:
            raise ProjetoInvalido(f"Grupo sem objetos no {where}.")
        extra = ob.GroupData(tuple(_parse_obj(c, f"{where}, item {k}", depth + 1)
                                   for k, c in enumerate(filhos, 1)))
    elif tipo == "vetor":
        extra = None
    else:
        raise ProjetoInvalido(f"Tipo de objeto desconhecido no {where}.")
    return (list_to_path(clean, fill == "winding"), tf, name, layer, color, extra)


def _texto(d, where):
    if not isinstance(d, dict):
        raise ProjetoInvalido(f"Dados do texto ausentes no {where}.")
    texto, fonte, alinh = _str(d, "texto", where), _str(d, "fonte", where), _str(d, "alinhamento", where)
    altura, esp = _num(d.get("altura_mm"), where), _num(d.get("espacamento"), where)
    negrito, italico = d.get("negrito"), d.get("italico")
    if not isinstance(negrito, bool) or not isinstance(italico, bool):
        raise ProjetoInvalido(f"Negrito/itálico inválido no {where}.")
    if alinh not in tx.ALINHAMENTOS or altura <= 0 or esp <= 0:
        raise ProjetoInvalido(f"Parâmetros de texto inválidos no {where}.")
    variavel = d.get("variavel", False)  # ausente em projetos até a versão 5
    if not isinstance(variavel, bool):
        raise ProjetoInvalido(f"Campo 'variavel' inválido no {where}.")
    peca = d.get("peca", 0)  # ausente até a versão 6
    if isinstance(peca, bool) or not isinstance(peca, int) or not 0 <= peca < 10_000:
        raise ProjetoInvalido(f"Campo 'peca' inválido no {where}.")
    extras = {k: d.get(k, False) for k in ("maiusculas", "soldado", "distorcer")}  # ausentes até a versão 16
    if not all(isinstance(v, bool) for v in extras.values()):
        raise ProjetoInvalido(f"Opções do texto inválidas no {where}.")
    return tx.TextoParams(texto, fonte, altura, negrito, italico, alinh, esp, variavel, peca, **extras)


def variaveis_from_dict(d) -> vr.DadosVariaveis:
    """Dados do texto variável (padrão vazio em projetos anteriores à versão 6)."""
    if "variaveis" not in d:
        return vr.DadosVariaveis()
    try:
        return vr.validar(d["variaveis"])
    except ValueError as e:
        raise ProjetoInvalido(f"Dados de texto variável inválidos: {e}.") from e


def gabarito_from_dict(d):
    """Gabarito do projeto, ou None (ausente antes da versão 7)."""
    if "gabarito" not in d:
        return None
    try:
        return gbm.de_dict(d["gabarito"])
    except ValueError as e:
        raise ProjetoInvalido(f"Gabarito inválido: {e}.") from e


def _imagem(d, where):
    if not isinstance(d, dict):
        raise ProjetoInvalido(f"Dados da imagem ausentes no {where}.")
    fmt, arquivo, sha = _str(d, "formato", where), _str(d, "arquivo", where), _str(d, "sha256", where)
    try:
        dados = base64.b64decode(_str(d, "dados", where), validate=True)
    except (ValueError, binascii.Error) as e:
        raise ProjetoInvalido(f"Imagem corrompida (base64) no {where}.") from e
    if hashlib.sha256(dados).hexdigest() != sha:
        raise ProjetoInvalido(f"Imagem corrompida (soma SHA-256 não confere) no {where}.")
    if im.detect_format(dados) != fmt:
        raise ProjetoInvalido(f"Formato da imagem não confere no {where}.")
    try:
        qimage = im.decode(dados)
    except im.ImagemInvalida as e:
        raise ProjetoInvalido(f"{e} ({where})") from e
    return im.ImagemOriginal(dados, fmt, arquivo, sha, qimage)


# ---------- arquivo ----------
def save(path: str, snapshots, camadas=(), variaveis=None, gabarito=None, ancoras=(), bloqueados=(),
         notas="", paginas=(None,), pagina_atual=0, nomes_paginas=None) -> None:
    """Grava atomicamente: escreve em .tmp e substitui; uma falha no meio não corrompe o arquivo anterior."""
    data = json.dumps(to_dict(snapshots, camadas, variaveis, gabarito, ancoras, bloqueados, notas, paginas,
                              pagina_atual, nomes_paginas),
                      ensure_ascii=False, indent=1)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load(path: str) -> list:
    return load_full(path)[0]


def load_full(path: str):
    """(objetos, camadas, texto variável, gabarito ou None, âncoras, bloqueados, notas, (páginas, atual))
    — tudo validado antes; objetos/âncoras/bloqueados são os da página aberta."""
    try:
        if os.path.getsize(path) > MAX_BYTES:
            raise ProjetoInvalido("Arquivo grande demais para ser um projeto.")
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, UnicodeDecodeError) as e:
        raise ProjetoInvalido(f"Não foi possível ler o arquivo: {e}") from e
    except json.JSONDecodeError as e:
        raise ProjetoInvalido(f"Arquivo corrompido (JSON inválido na linha {e.lineno}).") from e
    except RecursionError as e:  # JSON forjado com aninhamento extremo
        raise ProjetoInvalido("Arquivo com estrutura aninhada demais.") from e
    objs = from_dict(d)
    return (objs, layers_from_dict(d), variaveis_from_dict(d), gabarito_from_dict(d), ancoras_from_dict(d, len(objs)),
            bloqueados_from_dict(d, len(objs)), notas_from_dict(d), paginas_from_dict(d))
