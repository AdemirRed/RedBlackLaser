# RedBlack Laser no Claude e no Codex (servidor MCP)

O servidor MCP (`redblack/mcp_servidor.py`) deixa o Claude (Claude Code e Claude Desktop) e o Codex criar e editar
projetos `.rbl` e gerar G-code, conversando em português. Ele trabalha direto nos arquivos de projeto, sem abrir
janela, e **não envia nada à máquina** (o G-code é só gravado em arquivo).

Sem dependências extras: usa o próprio RedBlack (Python + PySide6 + pypdf). Protocolo MCP por stdio.

## Ferramentas
| Ferramenta | O que faz |
|---|---|
| `projeto_info` | abas, camadas (parâmetros), mesa e notas do projeto |
| `listar_objetos` | objetos de uma aba com tipo, camadas, posição e tamanho |
| `criar_projeto` | projeto novo com abas nomeadas |
| `adicionar_forma` | retângulo (raio de canto), elipse, círculo, polígono, estrela, linha, caminho SVG (curvas) e texto |
| `importar_arquivo` | SVG, DXF, PDF, AI (vetores) ou PNG/JPG (imagem) |
| `remover_objetos` | apaga objetos pelo nome |
| `configurar_camada` | velocidade, potência, passadas, modo, intervalo, kerf, saída, air… |
| `gerenciar_pagina` | adicionar, renomear, duplicar ou excluir abas |
| `gerar_gcode` | G-code de uma aba + tempo estimado e área (usa as Configurações da máquina do RedBlack) |
| `abrir_no_redblack` | abre o projeto na janela do programa |

Coordenadas: **mm, origem no canto superior esquerdo da mesa, X para a direita, Y para baixo**.

## Exemplos de pedido
- "Crie F:\Projetos\chaveiro.rbl com uma aba 'Chaveiros': um retângulo 50 × 25 mm com cantos de 4 mm em
  (10, 10), um furo de 5 mm na camada C02 a 6 mm da borda esquerda e o texto 'ADEMIR' com 8 mm de altura."
- "No projeto porta_cuia_e_termica.rbl, mostre as abas e gere o G-code da aba 'Bases' em F:\gcode\bases.gcode."
- "Configure a camada C01 para 250 mm/min, 100 %, 3 passadas, e abra o projeto no RedBlack."

## Instalado neste PC (2026-11-09)
- Claude Code (escopo usuário): `claude mcp list` mostra `redblack-laser ✔ Connected`.
- Codex: `codex mcp get redblack-laser`.
- Claude Desktop: entrada `redblack-laser` em `%APPDATA%\Claude\claude_desktop_config.json` (reinicie o Claude
  Desktop para carregar).

## Instalar em outro PC
Precisa do Python 3.10+ e do código do RedBlack. Na pasta do projeto:

```
pip install -r requirements.txt
claude mcp add --scope user redblack-laser -e PYTHONPATH=<pasta do RedBlack> -e QT_QPA_PLATFORM=offscreen -- python -m redblack.mcp_servidor
codex mcp add redblack-laser --env PYTHONPATH=<pasta do RedBlack> --env QT_QPA_PLATFORM=offscreen -- python -m redblack.mcp_servidor
```

Claude Desktop: em `%APPDATA%\Claude\claude_desktop_config.json`, dentro de `"mcpServers"`:

```json
"redblack-laser": {
  "command": "python",
  "args": ["-m", "redblack.mcp_servidor"],
  "env": {"PYTHONPATH": "<pasta do RedBlack>", "QT_QPA_PLATFORM": "offscreen"}
}
```

Remover: `claude mcp remove --scope user redblack-laser` e `codex mcp remove redblack-laser`.

## Limites
- O G-code nunca é enviado à máquina por aqui (nem pelo programa, nesta versão).
- Texto variável (planilha) e gabarito não são aplicados pelo MCP ao gerar G-code; use o programa para isso.
- Se o mesmo projeto estiver aberto no RedBlack, salvar no programa sobrescreve o que o MCP mudou (e vice-versa):
  feche ou reabra o projeto depois de usar o MCP.
