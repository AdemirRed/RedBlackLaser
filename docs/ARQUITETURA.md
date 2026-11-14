# Arquitetura

## Stack: Python 3.10 + PySide6 (Qt 6)
Escolhida porque já está instalada, é a mesma base Qt6 da referência, e cobre o que o plano exige:
`QGraphicsView` (edição gráfica), `QDockWidget` + `saveState` (painéis redimensionáveis/persistentes),
`QtSerialPort` (Etapa 13), `QSvg`. LGPLv3, permite distribuição. Alternativas consideradas:
C#/WPF (.NET 9/10 instalado) — bom, mas canvas vetorial e serial exigiriam mais código próprio;
Electron — pesado e sem vantagem para serial/desenho.

## Módulos (atual)
```
redblack/
  __main__.py        entrada: python -m redblack
  geometria.py       conversões documento↔exibição, passos de grade, ticks, distância (sem Qt)
  objetos.py         Shape (caminho + matriz) e transformações da seleção: mover, escalar,
                     girar, espelhar, alinhar, distribuir — todas em torno de um ponto explícito
  projeto.py         formato .rbl: serialização, validação na leitura, gravação atômica
  importar_svg.py    leitor SVG próprio (subconjunto explícito) → caminhos em mm + relatório do ignorado
  importar_imagem.py PNG/JPG: assinatura, DPI (pHYs/JFIF/EXIF), orientação EXIF, original imutável
  texto.py           TextoParams imutável -> contorno em mm (altura = X maiúsculo), fonte instalada?
  formas.py          caixa de arraste (Shift/Ctrl), retângulo, elipse, polígono, polilinha, nós
  camadas.py         Camada imutável (parâmetros), paleta C00–C15, validação de faixas
  percurso.py        documento + camadas -> Percurso (trechos corte/vazio, tempo, simulação); sem Qt widgets
  gcode.py           Percurso -> texto GRBL (perfil), verificação de limites, verificador que relê o texto
  simulador.py       controlador GRBL 1.1 simulado, determinístico (relógio virtual)
  transporte.py      interface de transporte: TransporteSimulado e TransporteSerial (QtSerialPort)
  variaveis.py       marcadores do texto variável, leitura de CSV, dados da planilha (imutáveis)
  gabarito.py        grade de células na mesa (produção em lote), validação; sem Qt
  encaixe.py         alvos de encaixe (cantos, centros, mesa) e o mais próximo dentro de um raio
  grbl.py            interpretação de mensagens GRBL (status, $$, boas-vindas) e avisos da máquina
  conexao.py         conexão SOMENTE LEITURA: lista de comandos permitidos, prazos, falhas
tools/simular.py     roda um G-code no simulador (transmissor de TESTE por contagem de caracteres)
  ui/painel_previa.py painel da prévia (resumo, tempo, simulação); ui/canvas.py: PercursoOverlay
  ui/dialogo_texto.py diálogo de criação/edição de texto
  ui/main_window.py  janela, menus, barras, docks, status, persistência de layout
  ui/canvas.py       área de desenho (cena em mm), réguas
  ui/icons.py        ícones SVG próprios
  ui/theme.py        tema escuro e foco visível
```
Módulos futuros (modelo, geometria, importação, planejamento, gcode, execução, transporte,
persistência) serão criados quando a etapa correspondente começar.

## Objetos e transformações
Cada objeto é um caminho fixo + uma matriz (`QTransform`). Uma operação monta a matriz em
coordenadas de cena (`T(-p) · op · T(p)`, p = ponto de referência) e a compõe depois da matriz
atual. Medidas usam o retângulo exato da geometria transformada (sem espessura de traço).
Durante um arraste de alça, as matrizes originais são restauradas a cada movimento, evitando
acúmulo de erro. O modelo de documento separado da cena virá com salvar/abrir (Etapa 4).

## Histórico (desfazer/refazer)
`QUndoStack` com um comando por edição que guarda o estado do documento antes e depois
(lista de snapshots + índices selecionados). Edições interativas avisam início/fim pela vista
(`editBegin`/`editEnd`); se nada mudou na geometria, nenhum passo é criado.

## Formato de projeto `.rbl` (versão 1)
```json
{"formato": "redblack-laser", "versao": 1, "criado_por": "RedBlack Laser x.y", "unidade": "mm",
 "objetos": [{"nome": "...", "camada": "C01", "cor": "#4aa3ff",
              "matriz": [m11, m12, m13, m21, m22, m23, m31, m32, m33],
              "preenchimento": "oddeven",
              "caminho": [["M", x, y], ["L", x, y], ["C", x1, y1, x2, y2, x, y]]}]}
```
Caminho em coordenadas locais + matriz completa = sem perda. Versões futuras incrementam
`versao`; arquivos de versão mais nova são recusados com mensagem clara.

Versão 2 (Etapa 6): campo `"tipo": "vetor" | "imagem"`. Imagens guardam o retângulo físico em mm
como `caminho` e o original em
`"imagem": {"formato": "png|jpeg", "arquivo": "...", "sha256": "...", "dados": "<base64>"}`.
Na leitura, base64, SHA-256, formato e decodificação são conferidos antes de aplicar.

Versão 3 (Etapa 7): `"tipo": "texto"` com `"texto": {texto, fonte, altura_mm, negrito, italico,
alinhamento, espacamento}`. O `caminho` guarda o contorno gerado; ao abrir, o contorno salvo é usado
(não é regerado), então a aparência não depende das fontes da máquina.

Versão 4 (Etapa 8): `"tipo": "grupo"` com `"filhos": [objetos]` (recursivo, até 32 níveis); matrizes
dos filhos são relativas ao grupo; o `caminho` do grupo é a união dos contornos (seleção e medidas).

Versão 5 (Etapa 9): `"camadas": [{id, nome, modo, velocidade_mm_min, potencia_max, potencia_min,
passadas, intervalo_mm, saida, visivel, air}]` na ordem de saída. Campos são exigidos exatamente
(nem faltando, nem sobrando) e validados por faixa.

Versão 6: `"variaveis"` (planilha, linha atual, contador). Versão 7: `"gabarito"` (colunas, linhas,
célula, vão, canto superior esquerdo em mm de documento) e `texto.peca` (posição no gabarito).

Versão 8: `camadas[].kerf_mm` (opcional na leitura; ausente = 0).

## Kerf
Só no modo Linha: `percurso.gerar` troca os contornos do objeto por `compensar_kerf(caminho em cena, k)` =
fronteira de (área preenchida ∪ traço de largura k, juntas redondas), calculada em µm. A regra de
preenchimento do próprio caminho define o que é material (furos encolhem). O documento não é alterado.

## Gabarito e texto variável
O documento passa a ser (objetos, seleção, camadas, texto variável, gabarito). Preencher copia a seleção
para cada célula e marca os textos variáveis com `peca = k`; o contexto do texto é o da linha atual + k
(`DadosVariaveis.peca`). A saída (prévia, G-code, lote) passa por `snaps_saida`, que descarta peças cuja
linha passou do fim da planilha. Gabarito e medidas são itens da cena que não são `Shape`: nunca entram no
percurso.

## Camadas
O documento é (objetos, seleção, camadas na ordem). Cada objeto folha guarda o id da camada; grupos
não têm camada própria. Após cada edição, `_ensure_layers` cria camadas recém-usadas e fixa o modo
Imagem nas que contêm imagens. Visibilidade é aplicada aos itens da cena; Saída só será lida pela
geração de G-code (Etapa 11). O histórico compara objetos **e** camadas.

## Percurso e estimativa
`percurso.gerar(snapshots, camadas)` é uma função pura do documento: percorre camadas na ordem
(só Saída), objetos folha (grupos expandidos com `matriz_filho · matriz_grupo`) e gera `Trecho`s
`corte`/`vazio` em mm de documento. Curvas são achatadas com tolerância de 0,0125 mm (o Qt achata a
0,25 em coordenadas já escaladas ×20). Preenchimento = varredura horizontal: cruzamentos
aresta×linha com intervalo semiaberto [ymin, ymax) (vértice conta uma vez), regra winding ou par-ímpar,
sentido alternado por linha. Tempo = comprimento/velocidade; a simulação usa tempos acumulados e
interpola dentro do trecho. A prévia é recalculada pela janela quando o documento muda e só enquanto
o painel está aberto. O módulo não conhece G-code, máquina nem porta serial.

## G-code
`gcode.gerar(percurso, camadas, perfil)` converte o mesmo `Percurso` da prévia (prévia e arquivo
nunca divergem na ordem). Conversão documento → máquina: `(x, altura − y)`. Limites e velocidades
são verificados antes de produzir texto. `gcode.analisar(texto)` é um interpretador mínimo e
independente do gerador, usado para conferir o arquivo antes de gravar e nos testes; servirá de base
ao simulador de controlador (Etapa 12). O módulo não abre portas nem conhece transporte.

## Simulador e transporte
O simulador só avança no tempo quando chamado (`avancar`), então os testes reproduzem exatamente
pausas, resets, alarmes e desconexões em qualquer instante. Ele registra cada segmento executado com a
potência efetiva (`trilha`) e o tempo de laser ligado parado (`emissao_parada_s`), permitindo provar que
deslocamentos saem apagados. O transporte expõe `abrir/fechar/escrever/ler_linhas/esperar`; a execução
(Etapa 15) só conhecerá essa interface, sem saber se fala com o simulador ou com a serial.

## Conexão (Etapa 13)
`Conexao` é uma máquina de estados (Desconectado → Conectando → Identificando → Conectado, ou Falha)
avançada por `tick(dt)`: a janela chama a cada 50 ms com um QTimer; os testes chamam direto com o
simulador. A lista `PERMITIDOS` é verificada ao agendar e de novo ao enviar (defesa em profundidade).
A serial é não bloqueante (`waitForReadyRead(0)`); perda do dispositivo vira `TransporteErro` e falha.

## Grupos
`GroupShape` guarda os filhos como snapshots imutáveis (`GroupData`). Agrupar copia a matriz de cena
de cada filho e começa com matriz identidade, portanto nada se move. Desagrupar compõe
`matriz_filho · matriz_grupo`. O grupo desenha os filhos (vetor, texto pelo contorno, imagem).

## Nós
Nós = pontos sobre a curva (MoveTo, LineTo e o ponto final de cada cúbica), sem o ponto repetido
que fecha um contorno. Mover um nó move junto os controles de entrada/saída e, se for o início de
um contorno fechado, o ponto de fechamento. A edição é feita em coordenadas locais (inversa da matriz).

## Texto
`TextShape` é um `Shape` cujo caminho vem de `build_path(params)`; o 6º campo do snapshot
(`extra`) guarda os `TextoParams`. Editar troca caminho e parâmetros mantendo a matriz.
"Converter em curvas" cria um `Shape` comum com o mesmo caminho e matriz.

## Imagens
`ImageShape` é um `Shape` cujo caminho é o retângulo físico (mm); a imagem decodificada é
desenhada dentro dele, portanto todas as transformações e medidas da Etapa 3 valem sem código
extra. `ImagemOriginal` é imutável e compara pelo SHA-256, para o histórico não comparar megabytes.

## Importação de SVG
Unidades do usuário SVG → mm por uma única matriz raiz (viewBox + width/height, 96 px/pol),
composta com os `transform` de cada nível. O caminho resultante já fica em coordenadas de
documento (SVG e documento têm origem no topo esquerdo e Y para baixo). Arcos são convertidos
em cúbicas de até 90° com extremos exatos. Nenhuma biblioteca de terceiros: `xml.etree` da stdlib,
com entidades XML recusadas antes da leitura.

## Sistemas de coordenadas
- **Cena**: mm, origem no canto superior esquerdo da mesa, Y para baixo (convenção Qt).
- **Exibição** (réguas/status): mm, Y = `BED_H − y_cena`, origem no canto inferior esquerdo.
- **Máquina**: não definida — depende do firmware confirmado (docs/MAQUINA.md).
- **Tela**: pixels; conversão só via `mapToScene`/`mapFromScene`. Escala uniforme (px/mm = `transform().m11()`),
  limitada a 0,2–200 px/mm. A cena se estende 2× a mesa em cada direção para permitir deslocar a vista.
