# Referência — LightBurn

Instalação: `C:\Program Files\LightBurn`, LightBurn Pro (Trial) 2.2.01, aplicação Qt6 (DLLs Qt6* presentes).
Primeira abertura nesta máquina mostrou o diálogo "Gestão de licenças" com a avaliação **não iniciada**;
o diálogo não foi tocado.

## Organização da janela principal (observação direta, captura de tela 2026-11-07)

Classificação: **confirmado** = visto na captura; **inferido** = deduzido sem uso da função.

| Área | Observação | Classe |
|---|---|---|
| Menus | Ficheiro, Editar, Ferramentas, Organizar, Ferramentas de laser, Ferramentas da Web, Janela, Emblaser Pro, Idioma, Ajuda (UI em pt-PT) | confirmado |
| Barra principal | novo/abrir/salvar/importar/exportar, desfazer/refazer, copiar/colar/excluir, mover, zoom, configurações, alinhamentos | confirmado |
| Barra de propriedades | PosX/PosY, Largura/Altura (mm e %), Girar, mm/in, controles de texto (fonte, altura, negrito…) | confirmado |
| Ferramentas | vertical à esquerda: seleção, edição de nós, linhas, retângulo, elipse, polígono, texto, medir, matriz… | confirmado |
| Área central | página branca com abas de página ("Página 1") | confirmado |
| Docks direita | "Cortes/camadas" (tabela #, Camada, Modo, Vel/Pot, Saída, Exibir, Ar + parâmetros), abas Câmaras, Texto variável, Pages | confirmado |
| Dock Laser | "Começar de", "Origem do trabalho" (9 pontos), dispositivos, otimização; aba "Biblioteca de materiais" | confirmado |
| Rodapé | paleta de cores de camada 00–29 + T1/T2; status com Mover/Tamanho/Girar/Cisalhar | confirmado |
| Docks destacáveis | ícones de flutuar/fechar nos títulos | confirmado |

## Navegação na área de trabalho (Etapa 2)

Fonte: documentação pública (não observada na instalação, bloqueada no diálogo de licença).
Classe: **documentado publicamente / não verificado localmente**.

| Comportamento | Fonte | RedBlack |
|---|---|---|
| Roda do mouse dá zoom em direção ao cursor; para frente aproxima | [Zooming and Panning](https://docs.lightburnsoftware.com/2.1/Reference/ZoomPan/) | igual |
| Opção para inverter a direção da roda | idem | não implementado |
| Botão do meio + arrastar desloca a vista | [Moving Around the Workspace](https://docs.lightburnsoftware.com/2.1/GetStarted/MovingAroundTheWorkspace/) | igual |
| Espaço + botão esquerdo desloca | idem | igual |
| `+`/`-` com a área focada; `Ctrl++`/`Ctrl+-` fora dela | [Hotkeys](https://docs.lightburnsoftware.com/Hotkeys.html) | igual |
| `Ctrl+0` = zoom na página | idem | igual ("Ajustar à mesa") |
| `Ctrl+Shift+A` = enquadrar seleção | idem | depende da Etapa 3 |

## Seleção e transformações (Etapa 3)

Fonte: documentação pública — [Numeric Edits Toolbar](https://docs.lightburnsoftware.com/latest/Reference/NumericEditsToolbar/),
[Transform Controls](https://docs.lightburnsoftware.com/latest/Reference/TransformControls/).
Não observado na instalação (diálogo de licença).

| Comportamento | Classe | RedBlack |
|---|---|---|
| Seletor de 9 pontos define referência de X/Y, âncora de redimensionamento e centro de rotação | documentado | igual |
| Objetos selecionados juntos são tratados como uma unidade; tamanho = menor retângulo que contém todos | documentado | igual (caixa alinhada aos eixos) |
| Trava de proporção: 50×25 com largura 80 vira 80×40 | documentado | igual; padrão ligado (padrão da referência não documentado) |
| Girar: positivo = horário | documentado | igual |
| Campo Girar é absoluto ou incremental | **não documentado** | decisão própria: incremental, volta a 0 |
| Shift ao arrastar canto: redimensiona sem manter proporção | documentado | igual |
| Shift ao girar arrastando: passos de 15° | documentado | igual |
| Campos em %, equações e unidades digitadas | documentado | não implementado |
| Shift+clique para adicionar à seleção | **não confirmado** | adotado (Ctrl também funciona) |
| Setas movem a seleção | **não confirmado** | adotado: 1 mm, Shift 10 mm |

## Importação de imagens (Etapa 6)

Fonte: fórum oficial — [Assumed resolution of PNG imported](https://forum.lightburnsoftware.com/t/assumed-resolution-of-png-imported/135681),
[Default size of imported images](https://forum.lightburnsoftware.com/t/default-size-of-imported-images/16773),
[Interpreted Image Sizes](https://forum.lightburnsoftware.com/t/interpreted-image-sizes/173939).
Relatos de usuários e da equipe, versões variadas; **não verificado na instalação**.

| Comportamento | Classe | RedBlack |
|---|---|---|
| Usa o DPI gravado na imagem (PNG/JPG/TIF) e o EXIF do JPEG | relatado pela equipe | igual (PNG pHYs, JFIF, EXIF) |
| Sem DPI: cai em ~96 dpi (há relato de 72 no macOS) | relatado por usuário | 96 dpi + aviso explícito |
| "DPI padrão" da referência vale só para SVG; DPI da camada reamostra na saída | relatado pela equipe | DPI de saída virá na Etapa 17 |

## Texto (Etapa 7)

Fonte: [Create and Edit Text](https://docs.lightburnsoftware.com/latest/Reference/Text/),
[Convert to Path](https://docs.lightburnsoftware.com/latest/Reference/ConvertToPath/),
[Text & Fonts (legado)](https://docs.lightburnsoftware.com/UI/FontsAndText.html). Não observado na instalação.

| Comportamento | Classe | RedBlack |
|---|---|---|
| Altura ≈ altura do X maiúsculo, aproximada e dependente da fonte | documentado | X maiúsculo exato |
| Arquivo com fonte ausente: aviso e carrega o contorno embutido; texto não editável até instalar | documentado | aviso + contorno salvo; edição permitida escolhendo outra fonte |
| Converter em caminho é permanente; letras viram formas separadas; grupos não convertem | documentado | permanente (desfazível); um objeto único |
| Edição digitando direto na área | documentado | diálogo |
| Alinhamento Y (topo/meio/base) e texto em caminho | documentado | não implementado |

## Formas, nós e grupos (Etapa 8)

Fonte: [Draw Shapes](https://docs.lightburnsoftware.com/latest/Reference/PrimaryShapes/),
[Creation Tools (legado)](https://docs.lightburnsoftware.com/UI/CreationTools.html),
[Grouping and Ungrouping](https://docs.lightburnsoftware.com/latest/Reference/Grouping/),
[Menus (legado)](https://docs.lightburnsoftware.com/UI/Menus.html). Não observado na instalação.

| Comportamento | Classe | RedBlack |
|---|---|---|
| Ctrl+R retângulo, Ctrl+E elipse | documentado | igual |
| Shift trava largura = altura; Ctrl desenha do centro | documentado | igual |
| Polígono: lados na janela de propriedades da forma | documentado | campo "Lados" antes de desenhar |
| Ctrl+G agrupa, Ctrl+U desagrupa | documentado | igual |
| Editar nós (Ctrl+`) só em caminhos não agrupados; formas primárias exigem converter em caminho | documentado | igual para grupos/texto; formas já nascem como caminhos |

## Camadas (Etapa 9)

Fonte: [Cuts / Layers Window](https://docs.lightburnsoftware.com/2.1/Reference/CutsLayersWindow/),
[Cuts and Layers (legado)](https://docs.lightburnsoftware.com/legacy/UI/CutsAndLayers),
[Cut Settings](https://docs.lightburnsoftware.com/latest/GetStarted/CutSettingsBeginner/),
[Image Mode](https://docs.lightburnsoftware.com/latest/Reference/CutSettingsEditor/ImageMode/). Não observado na instalação.

| Comportamento | Classe | RedBlack |
|---|---|---|
| Modos Linha / Preenchimento / Offset Fill; camada com imagem fica em Imagem | documentado | Linha / Preenchimento; Imagem fixo; Offset Fill não |
| Saída decide o envio ao laser; Exibir só esconde na tela (oculto ainda sai) | documentado | igual |
| Lista processada de cima para baixo | documentado | igual (▲/▼) |
| Passadas, potência máx./mín., intervalo (padrão 0,1 mm) | documentado | igual |
| Velocidade em mm/s ou mm/min (configurável) | documentado | mm/min fixo (unidade do G-code GRBL) |

## Prévia e estimativa (Etapa 10)

Fonte: [Preview](https://docs.lightburnsoftware.com/latest/Reference/Preview/),
[Previewing](https://docs.lightburnsoftware.com/latest/GetStarted/PreviewBeginner/),
[Inaccurate Time Estimates](https://docs.lightburnsoftware.com/latest/Troubleshooting/PreviewWindow/InaccurateTimeEstimates/).
Não observado na instalação.

| Comportamento | Classe | RedBlack |
|---|---|---|
| Cortes e deslocamentos sem laser distintos (preto × vermelho) | documentado | colorido na camada × cinza tracejado (cores próprias) |
| Distância sem laser e seu tempo mostrados separados | documentado | igual |
| Reprodução com velocidade ajustável (1/10× a 40×) | documentado | animação fixa de 15 s; sem ajuste de velocidade |
| Estimativa depende de aceleração e escalas de velocidade do dispositivo; pode ser lida do controlador | documentado | só comprimento ÷ velocidade; sem aceleração |
| Simula sobrevarredura de controladores DSP | documentado (página antiga) | não |
| Atalho Alt+P | **não confirmado** | adotado |

## G-code GRBL (Etapa 11)

Fontes: [Common GRBL setups](https://docs.lightburnsoftware.com/CommonGrblSetups.html),
[Sculpfun — setting up the software](https://sculpfun.com/blogs/blog/setting-up-the-software).
Saída real do LightBurn **não observada** (avaliação não iniciada; não foi gerado G-code pela referência).

| Comportamento | Classe | RedBlack |
|---|---|---|
| GRBL: $30 = 1000 e modo laser $32 = 1 | documentado (guia geral) | S 0–1000; cabeçalho exige $32=1 |
| SCULPFUN: dispositivo "GRBL-M3" | documentado pelo fabricante | M3 padrão; M4 opcional |
| Formato exato do arquivo da referência (cabeçalho, G0/G1, S/F modais) | **não verificado** | próprio |

## Protocolo GRBL (Etapa 12)

Fonte: [Grbl v1.1 Interface](https://github.com/gnea/grbl/wiki/Grbl-v1.1-Interface),
[Grbl v1.1 Commands](https://github.com/gnea/grbl/wiki/Grbl-v1.1-Commands),
[Grbl v1.1 Configuration](https://github.com/gnea/grbl/wiki/Grbl-v1.1-Configuration). Documentação do
firmware (não do LightBurn). Não observado em controlador real.

| Comportamento | Classe | Simulador |
|---|---|---|
| Cada linha → `ok` ou `error:N`; linha com erro é descartada | documentado | igual |
| `?`, `!`, `~`, Ctrl-X são tempo real e saem do buffer de recepção | documentado | igual (+ 0x85) |
| Status com `Bf:15,128` (blocos livres, bytes livres) | documentado | igual |
| ALARM:3 = reset durante movimento; posição não garantida | documentado | igual |
| Alarme trava G-code; poucos comandos aceitos | documentado | error:9 até $X/$H |
| Envio por contagem de caracteres (≤ 128 bytes sem resposta) | **não confirmado nesta pesquisa** | usado pelo transmissor de teste |

## O que o RedBlack Laser reaproveita
Só a **organização funcional** (onde ficam as coisas). Ícones, cores, textos e código são próprios.
