"""Texto variável: marcadores preenchidos por contador, data/hora e colunas de uma planilha CSV.

Marcadores (dentro de um texto marcado como variável):
  {n}      número de série atual        {n:3} com 3 dígitos (001, 002…)
  {data}   data (dd/mm/aaaa)             {hora} hora (HH:MM)
  {linha}  número da linha atual do CSV (1, 2, …)
  {Nome}   valor da coluna "Nome" do CSV (maiúsculas/minúsculas e acentos como no cabeçalho são
           aceitos sem diferenciar maiúsculas)
  {{ e }}  chaves literais
Marcador desconhecido continua visível como "{?nome}" para o erro aparecer na própria peça.

Os dados do CSV ficam no projeto (não dependem do arquivo original).
"""
import csv
import io
import re
from dataclasses import dataclass, replace
from datetime import datetime

MAX_BYTES = 2 * 1024 * 1024
MAX_LINHAS = 10_000
MAX_COLUNAS = 50
MAX_CELULA = 500
_TAG = re.compile(r"\{\{|\}\}|\{([^{}:]+?)(?::(\d{1,2}))?\}")


class CsvInvalido(Exception):
    """Planilha não pode ser usada; a mensagem é exibida ao usuário."""


@dataclass(frozen=True)
class DadosVariaveis:
    colunas: tuple = ()
    linhas: tuple = ()          # tuplas de textos, uma por linha do CSV
    arquivo: str = ""           # nome de origem (informativo)
    linha_atual: int = 0        # índice 0-based
    contador: int = 1
    incremento: int = 1

    def avancar(self):
        """Próxima peça: próxima linha (se houver) e contador + incremento."""
        prox = min(self.linha_atual + 1, max(len(self.linhas) - 1, 0))
        return replace(self, linha_atual=prox, contador=self.contador + self.incremento)

    def peca(self, k: int):
        """Dados da k-ésima peça a partir da atual (gabarito na mesa). A linha pode passar do fim da
        planilha: `contexto` deixa as colunas vazias e `sem_dados` avisa (a peça não vai para o laser)."""
        return replace(self, linha_atual=self.linha_atual + k, contador=self.contador + k * self.incremento)

    def sem_dados(self, k: int = 0) -> bool:
        return bool(self.linhas) and self.linha_atual + k >= len(self.linhas)

    def na_linha(self, i: int):
        return replace(self, linha_atual=max(0, min(i, max(len(self.linhas) - 1, 0))))


def contexto(d: DadosVariaveis, agora: datetime = None) -> dict:
    agora = agora or datetime.now()
    ctx = {"n": d.contador, "data": agora.strftime("%d/%m/%Y"), "hora": agora.strftime("%H:%M"),
           "linha": d.linha_atual + 1 if d.linhas and not d.sem_dados() else ""}
    if d.linhas:
        linha = () if d.sem_dados() else d.linhas[d.linha_atual]
        for i, col in enumerate(d.colunas):
            ctx.setdefault(col.casefold(), linha[i] if i < len(linha) else "")
    return ctx


def renderizar(modelo: str, ctx: dict):
    """(texto final, marcadores desconhecidos)."""
    faltando = []

    def troca(m):
        if m.group(0) == "{{":
            return "{"
        if m.group(0) == "}}":
            return "}"
        nome, digitos = m.group(1).strip(), m.group(2)
        chave = nome if nome in ("n", "data", "hora", "linha") else nome.casefold()
        if chave not in ctx:
            faltando.append(nome)
            return "{?" + nome + "}"
        v = ctx[chave]
        if digitos and isinstance(v, int):
            return str(v).zfill(int(digitos))
        return str(v)

    return _TAG.sub(troca, modelo), faltando


def tem_marcadores(texto: str) -> bool:
    return any(m.group(1) for m in _TAG.finditer(texto))


def ler_csv(dados: bytes, arquivo="") -> DadosVariaveis:
    """Primeira linha = cabeçalho. Aceita ; , ou tabulação; UTF-8 (com/sem BOM) ou Windows-1252 (Excel)."""
    if len(dados) > MAX_BYTES:
        raise CsvInvalido("Planilha grande demais (limite 2 MB).")
    try:
        texto = dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = dados.decode("cp1252", errors="replace")
    if not texto.strip():
        raise CsvInvalido("Planilha vazia.")
    amostra = texto[:4096]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t")
        sep = dialeto.delimiter
    except csv.Error:
        sep = ";" if amostra.count(";") >= amostra.count(",") else ","
    try:
        linhas = [ln for ln in csv.reader(io.StringIO(texto), delimiter=sep) if any(c.strip() for c in ln)]
    except csv.Error as e:
        raise CsvInvalido(f"Planilha com formato inválido: {e}") from e
    if len(linhas) < 2:
        raise CsvInvalido("A planilha precisa de um cabeçalho e pelo menos uma linha de dados.")
    cab = [c.strip() or f"coluna{i + 1}" for i, c in enumerate(linhas[0])]
    if len(cab) > MAX_COLUNAS:
        raise CsvInvalido(f"Colunas demais (limite {MAX_COLUNAS}).")
    dados_linhas = linhas[1:]
    if len(dados_linhas) > MAX_LINHAS:
        raise CsvInvalido(f"Linhas demais (limite {MAX_LINHAS}).")
    norm = tuple(tuple(c.strip()[:MAX_CELULA] for c in (ln + [""] * len(cab))[:len(cab)]) for ln in dados_linhas)
    return DadosVariaveis(tuple(cab), norm, arquivo)


def validar(d) -> DadosVariaveis:
    """Confere dados vindos do projeto (não confiáveis)."""
    if not isinstance(d, dict):
        raise ValueError("dados de texto variável inválidos")
    cols, linhas = d.get("colunas", []), d.get("linhas", [])
    if not (isinstance(cols, list) and all(isinstance(c, str) for c in cols) and len(cols) <= MAX_COLUNAS):
        raise ValueError("colunas inválidas")
    if not (isinstance(linhas, list) and len(linhas) <= MAX_LINHAS and all(
            isinstance(ln, list) and len(ln) == len(cols) and all(isinstance(c, str) for c in ln) for ln in linhas)):
        raise ValueError("linhas inválidas")
    ints = {k: d.get(k) for k in ("linha_atual", "contador", "incremento")}
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in ints.values()):
        raise ValueError("números inválidos")
    if linhas and not 0 <= ints["linha_atual"] < len(linhas):
        raise ValueError("linha atual fora da planilha")
    arquivo = d.get("arquivo", "")
    if not isinstance(arquivo, str):
        raise ValueError("nome de arquivo inválido")
    return DadosVariaveis(tuple(cols), tuple(tuple(ln) for ln in linhas), arquivo, **ints)


def nome_arquivo_seguro(texto: str, limite=40) -> str:
    s = re.sub(r"[^\w\-]+", "_", texto, flags=re.UNICODE).strip("_")
    return s[:limite] or "item"
