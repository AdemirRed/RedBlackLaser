# Instruções para agentes (Codex, Claude e outros)

Projeto: RedBlack Laser (PySide6), programa de corte/gravação a laser para GRBL. Respostas ao dono em português.

**Vai criar um projeto de corte/gravação (porta-retrato, presépio, peças a partir de PDF)?**
Leia antes [`docs/COMO_CRIAR_PROJETOS.md`](docs/COMO_CRIAR_PROJETOS.md): parâmetros obrigatórios (corte 630/85/2 no
MDF 3 mm, nunca 100 %, rebaixo 1500/60/1 passada + 0,1 mm por lado), os erros que já estragaram peças e o passo a
passo com os geradores de `tools/projetos/`.

Servidor MCP (criar/editar `.rbl` e gerar G-code conversando): [`docs/MCP.md`](docs/MCP.md).
Testes: `python -m pytest -q tests` (com `QT_QPA_PLATFORM=offscreen`).
