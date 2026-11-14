"""Plugin Orçamento: custo, preço de venda e lucro de uma peça (ex.: porta-retrato de 3 camadas) e do pedido.

Separação usada (para não confundir valor de referência com dinheiro que sai do bolso):
  • DESEMBOLSO por peça — MDF (chapa ÷ placas × camadas) + tinta (preço ÷ ml × ml por peça) + cola (kit ÷ peças por
    kit) + insumos + custo OPERACIONAL do laser (energia, manutenção, desgaste; R$/h real da máquina).
  • MÃO DE OBRA — tempo manual × sua hora.
  • REMUNERAÇÃO DA MÁQUINA — tempo de laser × (hora de laser cobrada − custo operacional/h).
  • CUSTO PARA PREÇO = desembolso + mão de obra + remuneração da máquina.
  • LUCRO = preço − custo para preço.  "Fica para você" = preço − desembolso (lucro + mão de obra + máquina).
Cada dado tem a marca "confirmado"; o resto aparece como ESTIMATIVA.
"""
import math

NOME = "Orçamento (custo, preço e lucro)…"
VALOR_HORA_PADRAO = 30.0


def calcular(tempo_s, valor_hora, material=0.0, outros=0.0, margem_pct=0.0, quantidade=1):
    """Conta simples (compatível com a versão antiga): tempo de máquina + material + outros, com margem."""
    if tempo_s < 0 or valor_hora < 0 or material < 0 or outros < 0 or margem_pct < 0 or quantidade < 1:
        raise ValueError("valores do orçamento não podem ser negativos")
    horas = tempo_s / 3600 * quantidade
    maquina = horas * valor_hora
    custo = maquina + (material + outros) * quantidade
    margem = custo * margem_pct / 100
    total = round(custo + margem, 2)
    return {"horas": horas, "maquina": round(maquina, 2), "material": round(material * quantidade, 2),
            "outros": round(outros * quantidade, 2), "custo": round(custo, 2), "margem": round(margem, 2),
            "total": total, "por_peca": round(total / quantidade, 2)}


# chave: (rótulo, padrão, tipo) — tipo: "dado" (pode ser confirmado/estimado) ou "decisao" (escolha sua)
CAMPOS = {
    "chapa_preco": ("Preço da chapa inteira de MDF", 44.0, "dado"),
    "placas_por_chapa": ("Placas que saem da chapa", 35, "dado"),
    "camadas": ("Camadas (placas) por peça", 3, "dado"),
    "tinta_preco": ("Tinta + pigmento (preço pago)", 46.0, "dado"),
    "tinta_ml": ("Tinta comprada (ml)", 900, "dado"),
    "tinta_ml_peca": ("Tinta gasta por peça (ml)", 30.0, "dado"),
    "cola_preco": ("Kit de cola (preço pago)", 39.0, "dado"),
    "cola_pecas": ("Peças montadas por kit de cola", 35, "dado"),
    "insumos": ("Outros insumos por peça (embalagem, fita…)", 0.0, "dado"),
    "laser_min": ("Tempo de laser por peça (min)", 0.0, "dado"),
    "custo_oper_hora": ("Custo OPERACIONAL do laser por hora (energia, manutenção, desgaste)", 0.0, "dado"),
    "hora_maquina": ("Hora de máquina (laser)", 50.0, "decisao"),
    "manual_min": ("Trabalho manual por peça (min)", 0.0, "dado"),
    "hora_manual": ("Sua hora de trabalho manual", 15.0, "decisao"),
    "fixos": ("Custos do pedido (frete, arte nova…)", 0.0, "dado"),
    "margem_pct": ("Margem sobre o custo (%) se não houver preço", 50.0, "decisao"),
    "preco_manual": ("Preço de venda por peça (0 = usar a margem)", 0.0, "decisao"),
    "quantidade": ("Quantidade de peças", 1, "decisao"),
}
INTEIROS = ("placas_por_chapa", "camadas", "tinta_ml", "cola_pecas", "quantidade")
DESCONTOS = ((1, 0.0), (5, 5.0), (10, 10.0), (20, 15.0))  # quantidade mínima → desconto % (editável na janela)

# Dados vindos do levantamento do usuário (APAGAR.txt, 13/11/2026). True = confirmado (compra/medida real).
CONFIRMADOS_INICIAIS = {"chapa_preco": True, "placas_por_chapa": True, "camadas": True, "tinta_preco": True,
                        "tinta_ml": True, "cola_preco": True}
MODELOS_INICIAIS = {
    "Tyfani": {"laser_min": 35.0, "manual_min": 10.0, "preco_manual": 60.0},
    "Valentina Hellena": {"laser_min": 20.0, "manual_min": 25.0, "preco_manual": 50.0},
}


def orcar(v):
    """`v`: dicionário com as chaves de CAMPOS. Devolve as parcelas por peça e do pedido."""
    for k, (_, padrao, _t) in CAMPOS.items():
        v.setdefault(k, padrao)
    if any(float(v[k]) < 0 for k in CAMPOS) or any(int(v[k]) < 1 for k in INTEIROS):
        raise ValueError("valores do orçamento inválidos (negativos ou zero onde não pode)")
    q = int(v["quantidade"])
    placa = float(v["chapa_preco"]) / int(v["placas_por_chapa"])
    mdf = placa * int(v["camadas"])
    tinta = float(v["tinta_preco"]) / int(v["tinta_ml"]) * float(v["tinta_ml_peca"])
    cola = float(v["cola_preco"]) / int(v["cola_pecas"])
    insumos = float(v["insumos"])
    horas_laser = float(v["laser_min"]) / 60
    oper = horas_laser * float(v["custo_oper_hora"])
    maquina_total = horas_laser * float(v["hora_maquina"])
    remun_maquina = max(0.0, maquina_total - oper)
    manual = float(v["manual_min"]) / 60 * float(v["hora_manual"])
    fixos_peca = float(v["fixos"]) / q
    desembolso = mdf + tinta + cola + insumos + oper + fixos_peca
    custo = desembolso + manual + remun_maquina
    preco = float(v["preco_manual"]) or custo * (1 + float(v["margem_pct"]) / 100)
    lucro = preco - custo
    r = {"placa": placa, "mdf": mdf, "tinta": tinta, "cola": cola, "insumos": insumos, "oper": oper,
         "fixos_peca": fixos_peca, "desembolso": desembolso, "manual": manual, "remun_maquina": remun_maquina,
         "maquina_total": maquina_total, "custo": custo, "preco": preco, "lucro": lucro,
         "fica_para_voce": preco - desembolso, "margem_real_pct": lucro / preco * 100 if preco else 0.0,
         "pecas_por_chapa": int(v["placas_por_chapa"]) // int(v["camadas"]),
         "sobra_placas": int(v["placas_por_chapa"]) % int(v["camadas"]),
         "chapas_pedido": math.ceil(q * int(v["camadas"]) / int(v["placas_por_chapa"])),
         "q": q, "custo_pedido": custo * q, "preco_pedido": preco * q, "lucro_pedido": lucro * q,
         "desembolso_pedido": desembolso * q}
    return {k: (round(x, 2) if isinstance(x, float) else x) for k, x in r.items()}


def tabela_descontos(v, faixas=DESCONTOS):
    """[(qtd mínima, desconto %, preço unitário, lucro unitário, fica para você/peça)] para pedidos maiores."""
    base = orcar(dict(v, quantidade=1))
    out = []
    for qmin, desc in faixas:
        r = orcar(dict(v, quantidade=qmin))
        preco = base["preco"] * (1 - desc / 100)
        out.append((qmin, desc, round(preco, 2), round(preco - r["custo"], 2), round(preco - r["desembolso"], 2)))
    return out


def dicas(r, v):
    """Ideias para aumentar a margem sem baixar a qualidade, a partir de onde o custo pesa mais."""
    out = []
    c = r["custo"] or 1
    if r["remun_maquina"] / c > 0.4:
        out.append(f"A hora de laser responde por {r['remun_maquina'] / c * 100:.0f} % do custo: menos minutos de "
                   "corte = mais margem. Teste velocidade e passadas na matriz de materiais e corte as 3 camadas de "
                   "várias peças na mesma placa.")
    if r["manual"] / c > 0.25:
        out.append("Trabalho manual pesa bastante: pinte a placa inteira ANTES de cortar (rolinho rende mais e "
                   "não marca), solte as sobras, lixe e cole em lote, use gabarito de colagem.")
    if float(v["tinta_ml_peca"]) >= 20:
        out.append("Meça a tinta de verdade: pese o pote antes e depois de pintar 5 peças. Pintar a placa antes do "
                   "corte costuma gastar menos que pintar peça por peça.")
    if r["sobra_placas"]:
        out.append(f"Cada chapa sobra {r['sobra_placas']} placa(s): use para peças pequenas (chaveiros, bases, "
                   "coroas) e venda junto como brinde ou adicional.")
    if r["margem_real_pct"] < 30:
        alvo = r["custo"] / (1 - 0.40)
        out.append(f"Margem real de {r['margem_real_pct']:.0f} %: para 40 % o preço por peça seria {reais(alvo)}.")
    if float(v["custo_oper_hora"]) == 0:
        out.append("Falta o custo operacional real do laser (energia + manutenção + desgaste por hora): sem ele o "
                   "lucro aparece maior do que é.")
    out.append("Personalização (nome, arte nova) pode ser cobrada à parte; o modelo base fica mais barato e o "
               "cliente que personaliza paga o tempo extra.")
    return out


def reais(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def registrar(janela, menu):
    from .janela import JanelaOrcamento
    estado = {"janela": None}

    def abrir():
        if estado["janela"] is None:
            estado["janela"] = JanelaOrcamento(janela)
        w = estado["janela"]
        w.atualizar_plano()
        w.show()
        w.raise_()
        w.activateWindow()
        return w

    acao = menu.addAction(NOME)
    acao.setToolTip("Custo, preço de venda e lucro da peça (MDF, tinta, cola, laser, trabalho manual)")
    acao.triggered.connect(abrir)
    janela.plugin_orcamento = {"abrir": abrir, "estado": estado}

