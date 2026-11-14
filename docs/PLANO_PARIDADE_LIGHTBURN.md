# Plano de paridade com o LightBurn (referência de funções)

Data: 2026-11-08. Objetivo: listar o que o programa de referência oferece e trazer para o RedBlack, com
**implementação própria** (nenhum código, ícone, texto de ajuda ou marca do LightBurn é copiado; só a lista de
funções e o comportamento observado servem de referência).

## Como o levantamento foi feito
- **REA**: `open_binary` em `C:\Program Files\LightBurn\LightBurn.exe` (PE x86_64, sha256 `1c7c1d2d…b4b3b`).
  `observe_native_ui` não está disponível no Windows ("Native macOS utilities require macOS") e a busca de textos
  no Ghidra expirou (executável grande demais para a análise em tempo útil). A sessão foi fechada.
- **Catálogo de textos da interface**: leitura (somente leitura) do arquivo de tradução
  `languages\LightBurn_pt-br.qm`: 7 084 textos em 262 telas/contextos (MainWindow 1 046, Configurações 208,
  Editor de corte 219, Configurações do dispositivo 246…). É a lista completa de menus, botões e opções.
- **Capturas** (só a janela do LightBurn, via PrintWindow; nenhum comando acionado, nada salvo nele):
  janela principal e os 9 menus. Árvore de acessibilidade da janela principal (botões e estados liga/desliga).
- Material em `C:\Users\RedBlack-PC\Documents\RedBlack_referencia_LightBurn\` (fora do repositório, por ser
  material de terceiros): `00_janela_principal.png`, `menu_01…09_*.png`, `arvore_janela_principal.txt`,
  `catalogo_textos_pt-br.md`.
- Diálogos capturados depois (computador ocioso há 2 h; LightBurn em primeiro plano conferido antes de cada
  clique; tudo fechado com Cancelar/Esc, nada salvo): Configurações (6 abas), Configuração do rotativo, Teste de
  intervalo, Gerador de teste de material, Dispositivos, Configurações do dispositivo (3 abas) — arquivos
  `dlg_*.png` e árvores `dlg_*_arvore.txt`. Diálogos que exigem seleção (Deslocar, Grelha/matriz) estão completos
  no catálogo de textos.

## Legenda
✅ já existe no RedBlack · 🟡 parcial · ⬜ falta · P1 = fazer agora (não depende da máquina) · P2 = depois ·
P3 = depende da máquina, de câmera/galvo ou de serviço externo (fica para as etapas do ROADMAP).

## 1. Arquivo
| Função de referência | RedBlack | Prioridade |
|---|---|---|
| Novo, Abrir, Salvar, Salvar como, Projetos recentes | ✅ | — |
| Importar (SVG, PNG/JPG) | 🟡 falta DXF, AI/PDF, HPGL, PCB | P2 (DXF), P3 (resto) |
| Exportar vetores selecionados / do projeto (SVG/DXF) | ⬜ | P2 |
| Salvar como modelo / modelos recentes | ⬜ | P2 |
| Imprimir, Impressão e corte | ⬜ | P3 |
| Exportar/importar preferências, pacotes | ⬜ | P2 |
| Salvar G-code | ✅ | — |

## 2. Editar
| Função | RedBlack | Prioridade |
|---|---|---|
| Desfazer/Refazer | ✅ | — |
| Histórico de anulações (lista) | ⬜ | P2 |
| Selecionar tudo | ✅ | — |
| **Inverter seleção** (Ctrl+Shift+I) | ⬜ | **P1** |
| Cortar (Ctrl+X) | ⬜ (há copiar/colar) | **P1** |
| Copiar, Colar, Duplicar, Excluir | ✅ | — |
| **Colar no lugar** (Alt+V) | ⬜ | **P1** |
| Converter em caminho | ✅ (texto → curvas) | — |
| Converter em bitmap | ⬜ | P2 |
| **Fechar caminho / fechar com tolerância** | ⬜ | **P1** |
| Associar automaticamente formas (juntar linhas) | ⬜ | P2 |
| Otimizar formas (recuperar arcos/linhas) | ⬜ | P2 |
| **Eliminar duplicados** (Alt+D) | ⬜ | **P1** |
| **Inverter direção da forma** | ⬜ | **P1** |
| **Selecionar formas abertas / abertas com preenchimento / da camada atual / contidas / menores / círculos** | ⬜ | **P1** |
| Opções de imagem (submenu) | ⬜ | P2 (Etapa 17) |
| Configurações (diálogo de preferências) | 🟡 algumas opções soltas | **P1** (ver §9) |

## 3. Ferramentas
| Função | RedBlack | Prioridade |
|---|---|---|
| Selecionar, Desenhar linhas, Editar nós, Editar texto, Medir | ✅ | — |
| Desenhar forma: retângulo, elipse, polígono | ✅ | — |
| **Desenhar forma: triângulo, pentágono, octógono, estrela, estrela dupla** | ⬜ | **P1** |
| **Aparar formas (tesoura, Ctrl+K)**: clicar num trecho entre cruzamentos para apagá-lo | ⬜ | **P1** |
| Editar nós: suavizar, converter em linha/canto, excluir/inserir nó, quebrar, aparar, estender, alinhar | 🟡 só mover nós | P2 |
| **Adicionar guias (tabs)** — pontes que seguram a peça | ⬜ | P2 |
| Criar código de barras / QR | ⬜ | P2 |
| **Deslocar formas (offset, Alt+O)**: para fora/dentro/ambos, cantos redondo/canto/bisel, apagar originais | ⬜ | **P1** |
| **Formas de solda (Ctrl+W)**, **União / Subtrair / Interseção booleana** | ⬜ | **P1** |
| Assistente de booleanas | ⬜ | P2 |
| **Cortar formas (cortador de biscoito, Alt+Shift+C)** | ⬜ | **P1** |
| Ajustar imagem, Traçar imagem (vetorizar), máscara, cortar imagem | ⬜ | P2/P3 (Etapa 17) |
| Aplicar caminho ao texto | ⬜ | P2 |
| Redimensionar ranhuras (slots) | ⬜ | P2 |
| Distorção 4 pontos / deformação 16 pontos | ⬜ | P3 |
| Gerar círculo tangente | ⬜ | P2 |

## 4. Organizar
| Função | RedBlack | Prioridade |
|---|---|---|
| Agrupar, Desagrupar | ✅ | — |
| Autoagrupar | ⬜ | P2 |
| Virar horizontal/vertical, Girar 90° | ✅ | — |
| **Espelhar ao longo da linha** (Ctrl+Shift+M) | ⬜ | **P1** |
| **Dimensionar/rodar por dois pontos** (Ctrl+2) | ⬜ | P2 |
| Alinhar (esquerda/direita/topo/base/centros) | ✅ | — |
| **Alinhar centros (H e V juntos)** | ⬜ | **P1** |
| Distribuir (centralizado) | ✅ | — |
| **Distribuir espaçado em H/V; mesma largura; mesma altura; Reunir em H/V** | ⬜ | **P1** |
| Otimização da disposição (nesting) | ⬜ | P3 |
| **Ancorar (dock) para cima/baixo/esquerda/direita** | ⬜ | **P1** |
| **Mover objetos selecionados para os 9 pontos da página** | ⬜ | **P1** |
| **Grelha/matriz (grid array)**: colunas, linhas, espaçamento, desloc., espelhar alternados, agrupar | 🟡 há gabarito | **P1** |
| **Matriz circular** | ⬜ | **P1** |
| Copiar ao longo do caminho | ⬜ | P2 |
| Contorno elástico a partir da seleção | ⬜ | P2 |
| Separar (Alt+B) | ✅ (Desagrupar/separar) | — |
| Ordem de desenho (PgUp/PgDown, frente/trás) | ✅ | — |
| **Bloquear / desbloquear formas** | ⬜ | **P1** |

## 5. Barras e status
| Função | RedBlack | Prioridade |
|---|---|---|
| Campos X/Y/Largura/Altura/%, Girar, travar proporção | ✅ (sem campos de %) | **P1**: escala % |
| **Interruptores na barra de status: Mover, Tamanho, Girar, Cisalhar** (liberar/impedir arrastar) | ⬜ | **P1** |
| Cisalhar ao arrastar | ⬜ | P2 |
| Barra de texto (fonte, altura, negrito, itálico, maiúsculas, soldado, espaçamentos, alinhar, distorcer) | 🟡 no diálogo de texto | P2 |
| Paleta de cores com 30 camadas + T1/T2 (ferramenta) | 🟡 16 camadas | P2 |
| Páginas | ⬜ | P3 |

## 6. Camadas (Editor de configurações de corte)
| Função | RedBlack | Prioridade |
|---|---|---|
| Modo Linha/Preenchimento/Imagem, velocidade, potência mín/máx, passadas, intervalo, ar, saída, exibir | ✅ | — |
| **Ângulo de varredura** (0 horizontal, 90 vertical) e incremento por passada | ⬜ | **P1** (frisos!) |
| **Varredura bidirecional (liga/desliga)** | 🟡 sempre bidirecional | **P1** |
| **Hachura cruzada** | ⬜ | **P1** |
| **Sobrevarredura (overscan)** | ⬜ | **P1** |
| Preencher todas as formas de uma vez / grupos / individualmente | 🟡 individual | P2 |
| Kerf (deslocamento de largura) | ✅ | — |
| Entrada/saída (lead-in/out), sobrecorte, perfuração, tempos de espera | ⬜ | P2 |
| Guias (tabs) automáticas por camada | ⬜ | P2 |
| Subcamadas | ⬜ | P2 |
| Modos de imagem (limiar, pontilhado Floyd/Jarvis/Stucki/Atkinson, escala de cinza) | ✅ (meio-tom falta) | — |
| Ativar/desativar/ocultar todas as camadas, inverter, "todas exceto esta", ar em todas | ⬜ | **P1** (menu de contexto) |

## 7. Otimização de corte
| Função | RedBlack | Prioridade |
|---|---|---|
| **Cortar primeiro as formas internas** (furos antes do contorno) | ⬜ | **P1** (segurança da peça) |
| **Escolher o melhor ponto de partida / reduzir deslocamentos (vizinho mais próximo)** | ⬜ | **P1** |
| Ordenar por camada / grupo / prioridade | 🟡 por camada | P2 |
| Remover linhas sobrepostas | ⬜ | P2 |
| Cortar na ordem de direção | ⬜ | P2 |

## 8. Laser (máquina)
| Função | RedBlack | Prioridade |
|---|---|---|
| Conectar, status | ✅ somente leitura | — |
| Enquadrar, ir à origem, mover laser, posição do usuário, começar de | ⬜ | P3 (Etapa 14, máquina) |
| Iniciar, pausar, parar, enviar, fila | ⬜ | P3 (Etapa 15) |
| Auxílio de ar | ⬜ | P3 (Etapa 16) |
| Rotativo | ✅ G-code (rolo/mandril, mm por rotação, diâmetro, espelhar); calibração na máquina pendente | — |
| Câmera, galvo, LiDAR, Wi-Fi | ⬜ | P3 (fora do escopo da S30) |
| Teste de material | ✅ (matriz de testes) | — |
| Teste de intervalo | ✅ (matriz: linhas = intervalo ou passadas) | — |
| Teste de foco | ⬜ | P3 (precisa de eixo Z) |

## 9. Configurações (preferências)
| Opção | RedBlack | Prioridade |
|---|---|---|
| **Intervalo de salvamento automático** | ⬜ | **P1** |
| **Inverter direção do zoom com a roda** | ⬜ | **P1** |
| **Incremento das setas e do Shift+seta** | ⬜ (1/10 mm fixos) | **P1** |
| **Distância de encaixe (pixels)** | ⬜ (12 fixo) | **P1** |
| **Mudar para seleção após desenhar** | ✅ sempre | **P1** (opção) |
| Unidades (mm/pol), DPI de importação SVG, centralizar ao importar, agrupar ao importar | 🟡 | P2 |
| Fonte e altura padrão do texto | 🟡 | **P1** |
| Antialiasing, qualidade da curva, tema | 🟡 | P2 |
| Teclas de atalho editáveis | ⬜ | P2 |

## Andamento (2026-11-08)
Todos os itens **P1** foram implementados e testados (334 testes automáticos), exceto onde indicado:
- Booleanas: deslocar formas (Alt+O), solda (Ctrl+W), união (Alt++), subtrair (Alt+-), interseção (Alt+*),
  cortar formas (Alt+Shift+C) — `redblack/booleanas.py`.
- Tesoura: Aparar formas (Ctrl+K), com realce vermelho do trecho antes do clique — `redblack/aparar.py`.
- Barra de status: ● Mover ● Tamanho ● Girar (liga/desliga, lembrados). Bloquear/desbloquear formas (salvo no
  projeto, versão 10). Cisalhar ficou para P2.
- Organizar: matriz em grade (com texto variável incrementando), matriz circular, encostar (dock), mover para
  os 9 pontos da página, distribuir espaçado, mesma largura/altura, alinhar centros, espelhar ao longo da linha.
- Editar: recortar, colar no lugar, inverter seleção, selecionar formas (abertas, abertas com preenchimento,
  da camada, contidas, menores, círculos), fechar caminho (com e sem tolerância), eliminar duplicados,
  inverter direção.
- Formas: triângulo, pentágono, hexágono, octógono (Ferramentas → Desenhar forma), estrela (ferramenta e
  Forma com medidas exatas).
- Camadas: ângulo de varredura, incremento por passada, bidirecional, hachura cruzada, sobrevarredura
  (projeto versão 11); menu de clique direito com ações em todas as camadas.
- Otimização: furos antes do contorno (padrão ligado), vizinho mais próximo com melhor ponto de partida.
- Configurações (Editar → Configurações): cópia automática, zoom invertido, passo das setas, encaixe,
  voltar para Selecionar, fonte/altura padrão do texto, otimização.
Itens **P2** também já feitos: escala em % na barra; histórico de anulações (painel); exportar SVG e DXF;
importar DXF (LINE, LWPOLYLINE com arcos, POLYLINE, CIRCLE, ARC, ELLIPSE); guias (pontes); sobrecorte;
preencher todas as formas de uma vez; operações de nós por teclas (D I M L C S B); copiar ao longo do caminho;
cisalhar; contorno elástico; código QR próprio (conferido com leitor independente); editor de teclas de
atalho; **gravação de imagens** (limiar, pontilhado, tons de cinza, negativo) — corrige o erro em que uma camada
de imagem queimava o retângulo inteiro.
Depois: ajuste de imagem (brilho/contraste/gama), encaixe na grade, remover linhas sobrepostas, barra de
texto, modelos de projeto, exportar/importar preferências, converter em bitmap, traçar imagem, texto ao longo
do caminho.
Depois: matriz com linhas = intervalo/passadas (teste de intervalo), rotativo no G-code, notas do projeto,
associar formas, imprimir 1:1, zoom à seleção, EAN-13.
Fora (decisão consciente): "espera/perfuração" — no modo laser do GRBL ($32=1) o feixe não emite parado, então
um G4 não perfuraria; a opção enganaria.

Também corrigidos a pedido: campo Girar mostra e guarda o ângulo; campo Raio mostra/troca o raio da peça.

## O que ainda falta (atualizado 2026-11-08, 17h)
As tabelas acima mostram a situação do início do dia; quase todo P1/P2 foi feito (ver "Andamento").
Continua faltando:
- **Depende da máquina (P3, etapas 14–16 do ROADMAP)**: conectar e mover o laser, enquadrar, origem/posição do
  usuário, iniciar/pausar/parar trabalho, enviar arquivo, auxílio de ar por comando, teste de foco, calibração do
  rotativo ("Testar"), câmera, galvo, LiDAR, Wi-Fi.
- **Edição**: nós — estender linha (E); dimensionar/rodar por dois pontos; cisalhar arrastando;
  redimensionar ranhuras; círculo tangente; assistente de booleanas; distorção 4/16 pontos.
- **Camadas**: subcamadas; entrada/saída (lead-in/out); frequência/PPI. (Meio-tom: feito em 2026-11-08.)
- **Arquivo**: importar AI/PDF/HPGL/Gerber; pacotes; páginas; nova janela; biblioteca de artes.
- **Configurações**: unidades em polegadas; tema; DPI de importação SVG.
- **Disposição automática (nesting)**.

## Ordem de execução (P1)
1. Booleanas: deslocar formas, solda, união, subtrair, interseção, cortar formas (mesma base geométrica).
2. Tesoura (aparar formas).
3. Barra de status: Mover/Tamanho/Girar; bloquear/desbloquear formas.
4. Organizar: grelha/matriz, matriz circular, ancorar, mover para a página, distribuir espaçado,
   mesma largura/altura, alinhar centros, espelhar ao longo da linha.
5. Editar: inverter seleção, cortar, colar no lugar, fechar caminho, eliminar duplicados, inverter direção,
   selecionar abertas/da camada/contidas/menores/círculos.
6. Formas: triângulo, pentágono, octógono, estrela.
7. Camadas: ângulo de varredura, bidirecional, hachura cruzada, sobrevarredura; ações de todas as camadas.
8. Otimização: furos antes do contorno e vizinho mais próximo.
9. Diálogo Configurações com as opções P1.

Cada item entra com testes automáticos e é registrado em PROGRESSO.md. Itens P2/P3 ficam neste documento como
lista de trabalho; P3 continua bloqueado pelas regras do plano (máquina conectada e confirmada).
