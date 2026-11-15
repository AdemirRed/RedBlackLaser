# Progresso

## Entrega atual — Etapa 13: comunicação serial e leitura de estado (2026-11-08)

Estado: **implementada e validada no simulador; validação na máquina real PENDENTE** (a SCULPFUN não
estava conectada: só existe a COM1 da placa-mãe). Não iniciar a Etapa 14 antes de conectar a máquina.

### Concluído
- Painel Máquina: porta (simulador ou portas listadas sob pedido), velocidade (115200 padrão),
  Conectar/Desconectar, estado da conexão e do controlador, posição de máquina, firmware, área
  ($130×$131), $30, $32, $22, $20, $110/$111, avisos, registro da comunicação e
  "Salvar relatório da máquina…" (JSON).
- **Somente leitura, garantido no código** (`redblack/conexao.py`): só envia `?`, `$I`, `$$`, `$G`.
  Movimento, laser, `$X`, `$H`, jog, reset, pausa e alterações de configuração são recusados.
  Alarme é mostrado, nunca desbloqueado.
- Conexão: espera as boas-vindas (placas que reiniciam ao abrir a porta) ou pergunta `?` (as que não
  reiniciam); prazos de resposta; falha clara (porta errada, baud errado, não é GRBL) e porta fechada.
- Reinício da placa durante a conexão é detectado e a identificação é refeita (só leitura); cabo
  removido vira falha com mensagem; **nada é retomado nem reconectado sozinho**.
- `redblack/grbl.py`: interpretação de boas-vindas (GRBL e FluidNC), status, `$$`, `[VER]`, `[OPT]`;
  dados vindos da porta tratados como não confiáveis (linhas truncadas, lixo descartado).
- `TransporteSerial` (QtSerialPort, 8N1, sem bloquear a interface); módulo serial só é carregado ao
  procurar portas ou conectar.
- Rodapé mostra "Máquina: conectado (…, somente leitura)" (antes era texto fixo).
- 206 testes automáticos passando (18 novos).

### Pendente (precisa da máquina)
1. Ligar a SCULPFUN por USB e confirmar que aparece uma porta COM (pode exigir driver do chip USB).
2. Procurar portas → escolher a porta → Conectar → Salvar relatório da máquina.
3. Preencher docs/MAQUINA.md com os valores lidos e confirmar o perfil do G-code (área, $30, $32).
4. Confirmar como o firmware real reage (boas-vindas, tempo de reinício ao abrir a porta).

### Limitações
- Não altera nenhuma configuração da máquina; o perfil do G-code (Etapa 11) ainda não usa os valores lidos.
- Velocidades de porta fixas na lista (115200, 250000, 57600, 9600).
- REA não utilizado (ver docs/REA.md).

### Próximo passo proposto (após a validação real)
Etapa 14 — movimentação, origem e enquadramento: movimentos graduais dentro dos limites lidos, com
laser desligado.

## Ajustes pedidos pelo usuário (2026-11-08)
- "DEMO" → "RedBlack": texto e nomes dos objetos de exemplo; materiais de exemplo passam a "[Exemplo]".
- **Encaixe em cantos e pontos** (`F9`, botão na barra; Alt segurado desliga na hora): Medir, retângulo,
  elipse, polígono, linhas, texto e edição de nós grudam em cantos/vértices, centros de objetos, cantos
  e centro da mesa e pontos da linha em desenho; marca amarela com o tipo ("canto", "centro", "mesa",
  "fechar"). Textos e imagens oferecem cantos e centro da caixa.
- **Correção — linha não fechava no ponto inicial**: só fechava a até 8 px, sem marca visível
  (reproduzido: desvio de 6 px na diagonal deixava aberta). Agora o início fica marcado, o cursor encaixa
  nele ("fechar") e a tolerância é de 12 px; fecha exatamente no ponto inicial.
- Correção: "Novo projeto" no meio de uma linha mantinha os pontos pendentes.
- Edição de nós: o nó vai exatamente para o cursor/encaixe (antes seguia o deslocamento do clique).
- 214 testes passando (8 novos).

## Pedido do usuário (2026-11-08): Duplicar e cantos arredondados
- **Duplicar (`Ctrl+D`, Editar → Duplicar)**: cópia no mesmo lugar (como a referência), cópias
  selecionadas para mover; textos continuam editáveis, grupos e imagens também; não usa a área de
  transferência; desfazível.
- **Cantos arredondados**: campo "Raio" (mm) na barra de propriedades.
  - Ferramenta Retângulo desenha já arredondado quando Raio > 0.
  - Organizar → Arredondar cantos: arredonda os cantos retos de retângulos, polígonos e linhas
    selecionados (raio em mm reais, mesmo após redimensionar); extremos de linhas abertas, curvas, textos,
    imagens e grupos ficam como estão (mensagem informa quantos foram ignorados); desfazível.
  - Raio maior que o possível é limitado à metade do lado mais curto (ex.: 40 × 20 com raio 100 vira
    "estádio" de raio 10), sem deformar a peça. Em polígonos, as pontas são aparadas: a caixa diminui.
- 222 testes passando (8 novos).

## Pedido do usuário (2026-11-08): texto variável e arquivos recentes
- **Texto variável**: opção no diálogo de texto, com prévia "Resultado agora". Marcadores `{n}`, `{n:3}`,
  `{data}`, `{hora}`, `{linha}`, `{Coluna}` (planilha, sem diferenciar maiúsculas), `{{`/`}}` literais;
  desconhecido aparece como `{?nome}` na peça e é avisado no painel.
- Painel **Texto variável** (aba ao lado de Camadas/Objetos): carregar planilha CSV (`;` `,` ou tabulação;
  UTF-8 ou Windows-1252 do Excel; limites 2 MB/10 000 linhas/50 colunas), tabela com a linha atual,
  Anterior/Próxima, número atual e incremento, Avançar (próxima peça), Remover planilha.
- Funciona dentro de grupos; prévia e G-code usam o valor atual; mudar linha/contador entra no desfazer.
- **Exportar G-code em lote** (Arquivo e painel): um arquivo por linha da planilha (ou N números de série),
  nome `projeto_001_João_da_Silva.gcode`; valida tudo antes de gravar; **não sobrescreve** arquivos
  existentes; não altera o documento.
- Projeto **versão 6**: planilha, linha atual e contador embutidos (abre sem o CSV original).
- **Abrir recente** (Arquivo): 8 últimos projetos (abrir/salvar), mais recente primeiro, sem repetidos;
  arquivo que não existe mais é avisado e sai da lista; "Limpar lista"; vale entre sessões.
- 234 testes passando (12 novos).

## Pedido do usuário (2026-11-08): gabaritos, produção em lote na mesa e medidas na tela
- Menu **Produção**: Gabarito na mesa…, Preencher gabarito com a seleção, Remover gabarito, Próxima mesa,
  Exportar G-code em lote.
- **Gabarito**: grade colunas × linhas de células (tamanho, vão, posição X/Y do canto superior esquerdo);
  recusa grade fora da mesa; guia na tela (não vai para o laser); guardado no projeto e desfazível;
  gabaritos salvos com nome nas configurações (reutilizáveis entre projetos).
- **Preencher**: uma cópia da seleção centrada em cada célula (ordem de leitura), nomes "Peça 001…";
  recusa desenho maior que a célula; desfazível. Cada texto variável guarda sua posição (`peca`) e usa a
  linha atual + posição da planilha; editar o texto mantém a posição.
- **Próxima mesa** avança N linhas (N = peças do gabarito); quando a planilha acaba, não avança.
  Peças sem linha mostram "—", são avisadas no painel e ficam **fora** da prévia, do G-code e do lote.
- **Lote**: com gabarito, um G-code por mesa (ex.: 5 nomes, 4 por mesa → 2 arquivos).
- **Medidas na tela** (`F10`, Ferramentas → Mostrar medidas, botão na barra; lembrado entre sessões):
  comprimento em cima da linha de Medir e do segmento da linha em desenho; largura/altura da seleção e da
  forma em desenho.
- Projeto **versão 7** (gabarito e `peca`); versões anteriores continuam abrindo.
- 246 testes passando (12 novos).

## Pedido do usuário (2026-11-08): girar peças no gabarito e materiais da S30 Pro Max 20 W
- Gabarito: campo **Girar peças na célula** (−360° a 360°, passos de 90° pelas setas); cabimento e centro
  calculados com a peça girada; "Célula do tamanho da seleção" usa a caixa girada; projetos v7 sem o campo
  continuam abrindo (giro 0).
- **Materiais** (adianta parte da Etapa 18, sem matriz de testes): 16 presets de referência da S30 Pro Max
  20 W (tabela de revendedor, marcados "não validado", fonte em docs/MAQUINA.md); "Aplicar à camada"
  (velocidade, potência, passadas, air assist, modo; camada de imagem só aceita gravação; desfazível);
  "Salvar camada como material…" e "Excluir" para presets próprios (guardados nas configurações).
- Rotativo: registrado em docs/MAQUINA.md; uso fica para a Etapa 19.
- 253 testes passando (7 novos).

## Pedido do usuário (2026-11-08): matriz de testes de materiais (Etapa 18)
- Laser → **Matriz de testes de materiais…** e botão no painel Materiais.
- Grade de até 20 × 20 quadrados: potência por coluna (de/até), velocidade por linha (de/até); gravação
  (preenchimento, intervalo) ou corte/contorno (linha); passadas, air assist (registrado; o G-code ainda não
  emite comando de ar), lado do quadrado, vão e posição.
- Rótulos gravados (potências em cima, velocidades à esquerda, vírgula decimal) com potência/velocidade
  próprias; podem ser desligados. Saem antes dos quadrados (num corte, as peças só se soltam no fim).
- "Faixa em volta do material selecionado": gravação = 50–150 % da potência e da velocidade do preset; corte =
  potência −20 até o valor do preset e 50–150 % da velocidade.
- Resumo ao vivo: número de quadrados, área com rótulos e tempo mínimo estimado; recusa faixa invertida,
  valores fora dos limites e matriz fora da mesa.
- Cada quadrado tem camada própria só dentro da matriz (comentário no G-code com potência e velocidade); o
  projeto não é alterado. Conferido pelo verificador e pelo simulador GRBL (25 quadrados: 6792 linhas, 0 erros,
  0 s de laser ligado parado).
- 259 testes passando (6 novos).

## Pedido do usuário (2026-11-08): salvar material direto pelo quadrado da matriz
- Materiais → **Salvar do quadrado escolhido…** e Laser → Salvar material do quadrado escolhido…: grade
  clicável na mesma posição da peça gravada (potências em cima, velocidades à esquerda); nome, espessura e
  observação; vira preset [Meu] com potência, velocidade, modo, passadas, intervalo e air assist da matriz.
- A última matriz exportada é lembrada entre sessões; o G-code da matriz guarda os parâmetros completos numa
  linha de comentário (`; RBMATRIZ {…}`), e "Abrir outra matriz (.gcode)…" reabre qualquer matriz gravada
  (dados do arquivo validados; arquivo que não é matriz é recusado com aviso).
- Simulador GRBL: G-code com a linha nova executa com 0 erros.
- 264 testes passando (5 novos).

## Pedido do usuário (2026-11-08): círculo Ø99,60, frisos e projeto porta-canetas
- **Forma com medidas exatas** (Ferramentas, `Ctrl+Shift+F`): círculo por diâmetro ou raio (campos ligados),
  elipse, retângulo com raio dos cantos, polígono; centro X/Y e camada.
- **Frisos para dobra** (Produção): N frisos de largura w com passo L/(N+1), margem opcional, calculadora
  L = π·(Di + 2t − e); contorno + frisos num só passo desfazível; camada dos frisos vai para Preenchimento e
  sai antes da camada do contorno.
- Projeto montado a partir de `blueprint_porta_canetas_100x150.pdf`: `F:\Downloads\porta_canetas_100x150.rbl`
  (lateral 330,4955 × 150 com 109 frisos de 0,30 mm, passo 3,004505; fundo Ø99,60; 3 cupons 60,09 × 50 com
  19 frisos de 0,30/0,60/1,00 mm; saída de todas as camadas DESLIGADA como pede o blueprint).
- Sem compensação de kerf automática (o blueprint pede medir k e aplicar k/2 depois).
- 270 testes passando (6 novos).

## Pedido do usuário (2026-11-08): compensação de kerf automática
- Camada ganha **Kerf (largura do corte)**, 0–2 mm, só no modo Linha (painel Camadas; desfazível).
- `percurso.compensar_kerf`: área do objeto ∪ traço de largura k (cantos redondos, como o feixe) → contorno
  deslocado k/2 para fora do material: peças crescem, furos encolhem. Operação em µm (precisão < 0,001 mm);
  lascas da operação booleana descartadas. Linhas abertas e preenchimento ficam como estão. O desenho não muda;
  vale para prévia, G-code, lote e matriz.
- Conferido: quadrado 20 → 20,2 e Ø99,60 → Ø99,80 com k = 0,2 (igual ao exemplo do blueprint); furo Ø20 → 19,8.
- Projeto **versão 8** (`kerf_mm` por camada); projetos anteriores abrem com kerf 0.
- `python -m redblack arquivo.rbl` abre o projeto direto.
- 276 testes passando (6 novos).

## Pedido do usuário (2026-11-08): renomear objetos
- Lista Objetos: duplo clique no nome ou F2 (Editar → Renomear objeto…); desfazível; nome vazio recusado;
  salvo no projeto. 278 testes passando (2 novos).

## Pedido do usuário (2026-11-08): medidas digitadas na tela e âncoras
- Clicar no rótulo de largura/altura da seleção abre uma caixa de digitação ali mesmo (Enter, Tab, Esc);
  digitar um número com objeto selecionado abre a largura com esse número. Usa a mesma regra dos campos da barra
  (proporção, ponto de referência); valor inválido não aplica; desfazível.
- **Âncoras**: Organizar → Prender à âncora (`Ctrl+Shift+A`; o 1º objeto selecionado é o pai) / Soltar da
  âncora. Presos não selecionados repetem a transformação do pai (mover, girar, escalar; ao vivo no arraste,
  setas, campos, alinhar…), em cadeia; ciclos recusados; apagar o pai solta os presos. Ligações tracejadas na
  tela e ícone na lista Objetos. Projeto **versão 9** (`ancoras` = pares de índices, validados).
- Fundo do projeto porta-canetas renomeado para "Fundo Ø99,60" (cópia de segurança do arquivo anterior no
  scratchpad da sessão).
- 285 testes passando (7 novos).

## Pedido do usuário (2026-11-08): desagrupar frisos e ordem dos objetos
- **Desagrupar / separar** (Ctrl+U): além de grupos, separa objetos com vários contornos (ex.: os frisos, que
  eram um único objeto composto) em um objeto por contorno, mantendo curvas, camada e posição; as partes ficam no
  lugar do original na lista; presos à âncora passam para a 1ª parte.
- **Ordem dos objetos = ordem de corte dentro da camada**: Organizar → Subir/Descer (PgUp/PgDown), Cortar
  primeiro/por último (Ctrl+PgUp/PgDown) e botões ▲ ▼ ⤒ ⤓ no painel Objetos; desfazível; âncoras mantidas.
- Desagrupar um grupo agora também mantém a posição na lista (antes ia para o fim).
- 290 testes passando (5 novos).

## Pedido do usuário (2026-11-08, trabalho autônomo): giro/raio e paridade com o LightBurn
- Correções: campo **Girar** mostra o ângulo atual e define o ângulo absoluto; campo **Raio** mostra o raio do
  retângulo selecionado e troca-o na peça (vale quantas vezes quiser; mm reais mesmo esticado/girado); sem
  seleção, é o raio dos próximos retângulos. A proteção de preenchimento foi recalibrada (frisos separados).
- Levantamento do LightBurn (REA + catálogo de textos + capturas só da janela dele):
  `docs/PLANO_PARIDADE_LIGHTBURN.md`; material bruto em `Documentos\RedBlack_referencia_LightBurn`.
- Implementado todo o P1 do plano (ver a seção "Andamento" do plano): booleanas e deslocar, tesoura,
  interruptores Mover/Tamanho/Girar, bloquear, Organizar (matrizes, encostar, página, distribuir, mesma medida,
  espelhar na linha), Editar (recortar, colar no lugar, inverter seleção, selecionar formas, fechar, duplicados,
  direção), estrela e polígonos prontos, varredura da camada (ângulo, bidirecional, hachura cruzada,
  sobrevarredura), ações de todas as camadas, otimização de corte e Configurações.
- Projeto **versão 11** (bloqueados e varredura); versões anteriores abrem com padrões.
- 334 testes passando.
- Continuação (P2): escala %, histórico de anulações, exportar SVG/DXF, importar DXF, guias (pontes),
  sobrecorte, preencher juntas, operações de nós (D/I/M/L/C/B), copiar ao longo do caminho, cisalhar,
  contorno elástico, código QR próprio, editor de atalhos.
- **Correção importante — imagens**: uma camada de imagem gerava preenchimento do retângulo inteiro (uma imagem
  branca dava 280 mm de laser ligado). Agora há gravação raster real (`redblack/raster.py`): limiar, pontilhado
  Floyd–Steinberg e tons de cinza com potência por ponto (S variável no G-code); branco nunca grava; imagem
  girada/espelhada acompanha. Simulador: 0 erros e 0 s de laser ligado parado. Projeto versão 14.
- Mais P2: ajuste de imagem (brilho, contraste, gama), encaixe na grade, remover linhas sobrepostas, barra de
  propriedades do texto, modelos de projeto, exportar/importar preferências, converter em bitmap, **traçar
  imagem** (vetorizar com furos), **texto ao longo do caminho**; teste de fumaça que dispara todos os comandos.
- Matriz de testes: linhas podem variar velocidade, **intervalo** (teste de intervalo) ou **passadas**.
- **Rotativo** (Laser → Configuração do rotativo…): rolo ou mandril, mm por rotação, diâmetros, espelhar; o
  G-code converte Y em giro da peça a partir do começo do trabalho; aviso vermelho na barra de status quando
  ativo; lembrado. NÃO validado na máquina (calibrar mm por rotação com a S30).
- Capturas dos diálogos do LightBurn (Configurações, rotativo, testes, dispositivos) — ver o plano.
- Notas do projeto (Ctrl+Alt+N, salvas no projeto, versão 16), associar formas (juntar pontas, Alt+J),
  imprimir em escala 1:1 (Ctrl+P / Ctrl+Shift+P), ajustar o zoom à seleção (Ctrl+Shift+0), código de barras
  EAN-13 próprio (conferido com leitor independente em todos os primeiros dígitos).
- Paleta ampliada para 30 camadas (C00–C29); otimizar formas (menos nós, Alt+Shift+O).
- **Correção de desempenho**: selecionar tudo com 500 objetos levava 64 s (verificação quadrática das
  âncoras + recálculo da janela a cada objeto). Agora seleções em massa e comandos recalculam uma vez só; a lista
  Objetos é montada de uma vez. 500 objetos: selecionar 0,09 s, duplicar 0,22 s; matriz com 1 500 cópias 1,1 s.
- Barra Texto: layouts salvos de versões antigas a deixavam cortada; o layout é refeito uma vez (versão 3).
- Ordem de corte com índice espacial em grade: 2 000 contornos — furos antes do contorno 1,8 s → 0,05 s;
  vizinho mais próximo 7,7 s → 0,09 s; resultado idêntico à comparação de todos contra todos (teste com 120
  casos aleatórios).
- Correções de lógica achadas na revisão: (1) guias + sobrecorte — o sobrecorte abria o contorno e as guias
  eram ignoradas sem aviso; agora as guias têm prioridade. (2) Gravação de imagem — os vãos dentro da linha eram
  deslocamentos rápidos (G0) e a sobrevarredura era repetida em cada trecho; agora cada linha é feita inteira na
  velocidade da camada com laser em zero nos vãos (G1 S0) e sobrevarredura só nas pontas (simulador: 0 erros).
- Autoagrupar (Organizar): externo + o que está dentro dele.
- Pontilhados Jarvis, Stucki e Atkinson (além de Floyd–Steinberg) na camada de imagem.
- Preferências › Importar: centralizar na mesa e agrupar o que vier de cada arquivo.
- Editar nós: tecla S deixa o nó suave (alças alinhadas).
- 407 testes passando.

## Pedido do usuário (2026-11-08, retomado após o PC desligar): configurações da máquina e botões
- **Laser → Configurações da máquina…** (botão de chave na barra Principal): largura e altura da área de
  trabalho, canto da origem (4 cantos), M3/M4, S máximo ($30) e velocidade máxima aceita. Aplica na hora
  (mesa e marca da origem redesenhadas, barra de status, prévia) e fica lembrado; valor salvo corrompido volta
  ao padrão. O G-code usa a mesa e a origem atuais (`gcode.doc_para_maquina`), e o percurso parte da origem
  e volta para ela. Padrão continua 400 × 400 mm, origem inferior esquerda, M3, S 1000 (NÃO verificado na
  S30 — conferir $130/$131/$30/$110 pelo relatório da máquina).
- Botões que faltavam (comparados com a captura do LightBurn): barra Principal — mover a vista (H),
  ajustar à seleção, configurações da máquina, agrupar/desagrupar, espelhar H/V, espelhar na linha, alinhar
  centros, 6 alinhamentos, distribuir H/V; barra Ferramentas — deslocar, solda, união, subtração, interseção,
  matriz em grade, matriz circular, copiar ao longo do caminho. Ícones próprios; mesmos comandos dos menus.
- Barra Texto: **Maiúsculas**, **Distorcer** (no texto ao longo do caminho as letras curvam junto) e
  **Soldado** (letras fundidas num contorno). Significado conferido no catálogo de textos do LightBurn
  (REA). Projeto **versão 17**; versões anteriores abrem com as opções desligadas.
- 417 testes passando (10 novos).
- Camada de imagem: modo **Meio-tom** (pontos redondos em grade girada; a área de cada ponto acompanha o tom),
  com "Meio-tom: células por polegada" (padrão 50) e "Meio-tom: ângulo" (padrão 45°), como no LightBurn
  (opções conferidas no catálogo de textos). Cobertura medida: tom 25/50/75 % grava 25/50/75 % (±6 %).
- 421 testes passando.
- **Guias inteligentes ao arrastar**: bordas e centro da seleção grudam nas bordas e centros dos outros
  objetos e da mesa (dentro do raio de encaixe), com linha rosa tracejada mostrando cada alinhamento; somem ao
  soltar; um desfazer volta tudo. Desligam com o Encaixe (F9) ou segurando Alt (`encaixe.guias_alinhamento`).
- **Botão direito na área de desenho**: copiar, recortar, colar, duplicar, excluir, agrupar, desagrupar,
  espelhar, alinhar, converter em curvas, renomear (seleciona o objeto sob o clique).
- 427 testes passando.
- **Comparativo atualizado** com o LightBurn: `docs/COMPARATIVO_LIGHTBURN.md` (o que temos e o que falta).
- **Versão 0.14.0 para distribuir**: ícone próprio (`tools/gerar_icone.py`), créditos "© 2026 RedBlack. Todos os
  direitos reservados. Desenvolvido pela RedBlack com o assistente de IA Claude Opus (Anthropic)." na tela Sobre,
  nas propriedades do EXE, no instalador e em `instalador/LICENCA.txt` (termos de uso, aviso de segurança do
  laser, LGPL do Qt). Gerar tudo: `powershell -ExecutionPolicy Bypass -File instalador\gerar.ps1` →
  `dist\RedBlackLaser-0.14.0-Setup.exe` (instalador, sem pedir administrador, atalhos, abre .rbl) e
  `dist\RedBlackLaser-0.14.0-portatil.zip`. Conferido: EXE abre um projeto; instalação e desinstalação
  silenciosas funcionam.

## Continuação (2026-11-08): itens do comparativo
- **Disposição automática na mesa** (Organizar, Ctrl+Alt+D; `redblack/disposicao.py`, MaxRects): arruma a
  seleção (ou tudo) sem sobrepor, com espaço, margem e giro de 90°; objetos não envolvidos e bloqueados ficam e
  são contornados; peças que não cabem ficam onde estavam. Pelo retângulo de cada peça (não pela forma).
- **Entrada/saída do corte** (camada, modo Linha): reta perpendicular do lado da sobra (fora da peça, dentro
  dos furos), não sai da mesa; não vale com guias. Projeto versão 17.
- **Reunir em H/V**, **Redimensionar slots** (`redblack/ranhuras.py`: slots retos e furos retangulares,
  centrados) e **Dimensionar/rotacionar por dois pontos** (Ctrl+2, três cliques com encaixe, Esc cancela).
- Versão 0.15.0; instalador refeito. 451 testes passando.
- **Subcamadas** (painel Camadas): passes extras sobre os mesmos objetos logo depois da camada (modo, velocidade,
  potência, passadas, intervalo, ângulo próprios; o resto vem da camada). Viram camadas virtuais "C01.1"… em
  `cm.expandir`, usadas pelo percurso, prévia e G-code. Salvas no projeto (versão 17).
- Correção: ao trocar de camada, os campos de meio-tom e de entrada/saída não eram atualizados (mostravam os da
  camada anterior).
- **Importar PDF e AI** (Illustrator com compatibilidade PDF): desenhos vetoriais da 1ª página, com blocos
  (Form XObjects); texto e imagens dentro do PDF são avisados e não entram; recortes não viram objetos.
  Leitor próprio sobre o pypdf (BSD) — o PyMuPDF foi evitado por ser AGPL.
- Versão 0.16.0. 461 testes passando.
- **Páginas** (abas acima da mesa: + nova, ⧉ duplicar, − excluir): cada página tem seus objetos, âncoras e
  bloqueios; camadas, texto variável e gabarito são comuns; prévia e G-code usam só a página aberta. Adicionar/
  duplicar/excluir se desfazem; trocar de página não entra no histórico, mas o desfazer leva à página da
  alteração. Projeto **versão 18** (`paginas` + `pagina_atual`; antigos abrem com uma página). A barra de abas
  tem altura fixa (com o tema, ela crescia 1 px depois de aberta e deslocava a mesa).
- Versão 0.17.0. 466 testes passando.
- **Abas como no Excel**: as páginas ficam embaixo da mesa e têm nome (duplo clique renomeia; desfazível;
  salvo no projeto em `nomes_paginas`). Duplicar cria "<nome> (cópia)".
- **Projeto Porta-cuia e térmica** (pedido do usuário, PDF R03 MDF 6 mm): gerador
  `tools/projetos/porta_cuia_termica.py` → `F:\Downloads\porta_cuia_e_termica.rbl`, com 5 abas (gabarito +
  4 folhas de produção), 12 peças agrupadas, furos/rasgos em C02 (corta primeiro) e contornos em C01, notas
  de montagem. Medidas conferidas contra o PDF em `tests/test_projeto_porta_cuia.py` (envoltórias, furos,
  G-code de cada aba dentro de 370 × 360 mm). O gabarito de encaixes foi desenhado a partir da tabela da
  pág. 4 (o PDF não dá todas as cotas dele).
- Versão 0.18.0. 470 testes passando.
- **Curvas à mão**: (1) Linhas: clicar e ARRASTAR antes de soltar dá alça ao ponto (curva de Bézier suave, alça
  de entrada espelhada); só clicar = canto reto. (2) Editar nós mostra e deixa arrastar as alças das curvas
  (bolinhas amarelas ligadas ao nó). (3) Tecla L alterna o trecho entre reta e curva (era só curva→reta).
  (4) Grupo, texto ou imagem no Editar nós: a barra de status explica o que fazer (desagrupar / converter).
- Versão 0.19.0. 476 testes passando.
- **Servidor MCP** (`redblack/mcp_servidor.py`, sem dependências): Claude e Codex criam/editam projetos .rbl
  (abas, formas, curvas SVG, textos, importação, camadas) e geram G-code; abre o projeto no programa. Registrado
  neste PC no Claude Code (usuário), Codex e Claude Desktop. Ver `docs/MCP.md`. Gerar instalador: cada versão
  agora vai para `dist\<versão>\` (um RedBlack aberto não trava mais a geração). 480 testes passando.
- **Régua (Medir)**: a medida aparece sempre em cima da linha (mesmo com "Mostrar medidas" desligado), maior e com
  tracinhos nas pontas. **Encaixe "na linha"**: sem canto/centro por perto, a régua (e o desenho) gruda no ponto
  mais próximo de qualquer contorno — meio de reta ou de curva, também dentro de grupos (marca X "na linha").
- **Porta-cuia para qualquer espessura**: o gerador virou `Projeto(t)`; com t = 6 reproduz as cotas do PDF
  (teste), com t = 3 gera `F:\Downloads\porta_cuia_e_termica_3mm.rbl` (rasgos 3,15/6,15, machos 3/6, gabarito
  2,70–3,30 e 5,70–6,30, 1 passada). Testes conferem que cada macho cai no seu rasgo.
- Versão 0.20.0. 489 testes passando.
- **Visual**: fundo da mesa "Cinza neutro" (claro, sem ser branco) por padrão, com grade mais escura; linhas dos
  desenhos com 2,5 px (antes 1,5). Configurações → Visual: fundo (Cinza neutro, Grafite, Escuro) e espessura
  (1 a 6 px). Marcas amarelas (régua, encaixe) com contorno escuro; origem em âmbar escuro.
- Montagem conferida: teste que põe cada parede no piso e confere 13 linguetas em 13 rasgos (3 e 6 mm).
- Versão 0.21.0. 491 testes passando.
- **Clique pega o objeto de dentro**: com uma peça dentro da outra (furo dentro da base desagrupada), o clique
  seleciona a MENOR sob o cursor; a de fora se pega pela borda ou fora dos furos (`BedView._mais_de_dentro`).
- **Linhas de distância**: com seleção e "Mostrar medidas" ligado, linhas rosa saem do meio de cada lado até o
  primeiro contorno (ou a borda da mesa) com o valor em mm; clicar no número e digitar move o objeto para aquela
  distância (ex.: furo a 3 mm da borda). `encaixe.distancias_lados` / `deslocamento_para`. Alças têm prioridade
  sobre o clique nos números.
- Versão 0.22.0. 497 testes passando.
- **Área de clique como na referência**: peças grandes se pegam pela LINHA (6 px de margem); o miolo vazio fica
  livre para a caixa de seleção (agora dá para selecionar furos arrastando a caixa por dentro da base). Peças
  pequenas na tela (< 24 px, ex.: furos com zoom longe), textos e imagens: clique em qualquer ponto de dentro.
  `Shape.shape()` com cache; folga fixa no `boundingRect` (o índice da cena não muda com o zoom).
- Versão 0.23.0. 499 testes passando.
- **Seleção revista** (pedido do usuário): (1) cada peça selecionada é desenhada tracejada em rosa (antes só a
  caixa geral aparecia); (2) peça comum: clicar/arrastar por dentro seleciona e move de novo; (3) peça com outras
  dentro (base com furos): arrastar pelo miolo vazio faz a caixa de seleção, clique rápido seleciona a peça, e
  depois de selecionada arrasta por dentro; pela linha sempre move; (4) caixa de seleção pega o que está inteiro
  dentro e o que tem a LINHA cruzada (o miolo da base não conta). Números das linhas de distância fora da linha.
- Versão 0.24.0. 504 testes passando.
- **Plugin Plano de corte** (Ferramentas → Plugins; não mexe no layout): janela Qt própria com abas Peças /
  Materiais & Chapas / Plano de corte / Config (inspirada no "CorteCerto-Clone.html" do usuário, mas em Python como
  o resto do sistema, a pedido dele): tabela editável (Qtd, Largura, Altura, Material, Descrição, Gira), CSV,
  lista salva em AppData. Encaixe MaxRects por material (`plugins/plano_corte/plano.py`), com espaço, margem e
  "Gira" por peça; várias chapas. "Enviar ao RedBlack" cria uma aba por chapa no projeto aberto (peças na camada
  escolhida, borda da chapa em C29 sem saída). `redblack/plugins/` registra plugins só no submenu.
- Versão 0.25.0. 513 testes passando.
- **Ferramenta Bolear** (barra lateral, Ctrl+Shift+R): clique perto de um canto boleia só ele; clique na peça
  boleia todos; Shift+clique deixa as pontas totalmente redondas (raio = metade do lado menor, como a pega da
  alça). Raio = campo Raio da barra (5 mm se zerado). Prévia em vermelho sob o mouse. Funciona em formas que já
  têm curvas (`nos.bolear` / `nos.cantos_boleaveis`); medida externa não muda.
- Versão 0.26.0. 520 testes passando.
- **Abrir grupo** (pedido do usuário: não precisar desagrupar): duplo clique no grupo (área de desenho ou lista),
  botão 📂 no painel Objetos ou botão direito. As peças ficam editáveis uma a uma e aparecem como filhas do nó
  "📂 nome" na lista (marcar o pai seleciona todas); 📁 Fechar grupo junta de novo com o mesmo nome e lugar.
  Fecha sozinho ao salvar e ao trocar/criar/excluir aba; desfazer/refazer lembram o grupo aberto (doc_state).
  Grupos fechados mostram as peças na lista (só para ver).
- Campos da barra (X, Y, Largura, Altura, %, Girar) aplicam enquanto digita (pausa de 0,5 s) — antes só no Enter.
- Réguas: a área de desenho avisa qualquer rolagem (barras/teclado), não só zoom/arraste.
- Versão 0.27.0. 526 testes passando.
- Correção: Estrela e Polígono saíam triângulo depois de usar "Desenhar forma → Triângulo" (dividiam o campo
  Lados). Agora a Estrela tem as próprias pontas (5) e o campo da barra mostra Lados ou Pontas conforme a
  ferramenta.
- **Formas prontas** (`redblack/formas_prontas.py`): segurar o botão de retângulo/elipse/polígono/estrela (ou a
  setinha) abre o menu — triângulos, losango, pentágono, hexágono, octógono, estrelas 4/5/6/8, coração, seta, cruz,
  balão de fala, oblongo (pega); arrasta-se a caixa na mesa. Também em Ferramentas → Desenhar forma.
- **Contorno retangular ao redor** (Organizar): retângulo/quadrado em volta da seleção com margem e raio
  (Deslocar segue a forma — em volta de círculo dá círculo).
- **Pesquisa de comandos (F4)**: acha qualquer comando dos menus e barras pelo nome (sem acento) e executa.
- Bolear: ao ligar, o campo vira "Raio do bolear" (destacado e pronto para digitar; 5 mm se zerado) e a prévia
  acompanha o raio digitado.
- Versão 0.28.0. 532 testes passando.
- **Renomear grupos**: duplo clique na lista (ou F2) renomeia qualquer objeto, inclusive grupo e grupo aberto
  (o nome fica ao fechar). Abrir grupo: duplo clique na mesa, botão 📂 ou botão direito.
- **Solda/União** não engolem mais o que está inteiro dentro de outra peça selecionada (texto, furo, gravação em
  cima da placa): só se juntam as que se sobrepõem; as de dentro ficam como estão.
- **Bolear como no original**: campo de raio logo abaixo do botão; prévia ao passar o mouse no canto; clique =
  redondo, de novo = 45°, de novo = canto vivo (`nos.cantos_redondos/chanfrar/chanfros/canto_vivo`).
- **Cisalhar (tirar do esquadro)**: interruptor "Cisalhar" na barra de status; com ele ligado, as alças do meio dos
  lados inclinam a peça (X pelas de cima/baixo, Y pelas laterais) em vez de esticar.
- **Dicas animadas**: parar o mouse num botão da barra de ferramentas mostra nome, explicação e uma animação curta
  da ferramenta (desenhada pelo programa; Configurações → Visual liga/desliga). `ui/dica_animada.py`.
- Versão 0.29.0. 537 testes passando.
- **Preenchimento visível na tela**: objetos de camada no modo Preenchimento aparecem com o miolo pintado na cor da
  camada (translúcido; furos respeitados); Linha continua só contorno (`objetos.PREENCHIDAS`).
- `tools/plano_corte_pdf.py`: plano de corte em PDF de qualquer .rbl (chapa numerada, ordem/parâmetros das camadas,
  tempo estimado, lista de peças e notas). `tools/projetos/escorpiao_62.py` (+ `_blender.py`): projeto 62 R02/R03.
- Versão 0.29.1. 538 testes passando.
- **Peça de grupo fechado na lista Objetos**: clicar nela seleciona o grupo e destaca a peça na mesa (rosa
  preenchido, `BedView.destacar`); some quando a seleção muda na mesa.
- Versão 0.29.2. 539 testes passando.
- **Colar de outros programas (Ctrl+V)**: imagem copiada (navegador, Paint, print) vira objeto de imagem a 96 dpi no
  centro da tela; arquivos copiados no Explorer são importados; código SVG copiado é importado; texto vira objeto de
  texto. A cópia interna marca a área de transferência (`MIME_INTERNO`) e continua tendo prioridade.
- **Traçar imagem como no original** (Alt+T): janela com prévia ao vivo (`ui/dialogo_tracar.py`), Corte e Limiar
  (faixa de brilho 0–255), Ignorar menores que, Suavidade (curvas), Otimizar, Traçar transparência, Traçar esboço
  (média local), Linha central (afinamento Zhang–Suen), Inverter, Apagar imagem depois, Esmaecer imagem, Mostrar
  pontos e área arrastada na prévia (Limpar área). Opções observadas nos textos da tela do LightBurn.
- Versão 0.30.0. 548 testes passando.
- Janela Traçar imagem no layout do original (prints do usuário): prévia grande em cima, traçado em magenta, Corte/Limiar
  com campo + barra, botões Desbotar imagem / Mostrar pontos / Limpar limite.
- **Ajustar imagem (Alt+I)** (`ui/dialogo_ajustar_imagem.py`): original × "como o laser vai gravar" ao vivo; modo,
  brilho, contraste, gama, limiar, intervalo, inverter (gravados na camada da imagem).
- **Salvar bitmap processado**: PNG do que o laser grava, um pixel por linha (`raster.imagem_processada`).
- Menu do botão direito na ordem do original: Cortar, Copiar, Colar, Colar no lugar, Duplicar, Excluir, Selecionar
  tudo, Agrupar/Desagrupar/Abrir/Fechar grupo, Bloquear, Converter em curvas/bitmap, Prévia, Traçar imagem, Ajustar
  imagem, Salvar bitmap processado, Alinhar e espelhar (submenu), Renomear.
- Versão 0.31.0. 549 testes passando.
- Correção: Colar (Ctrl+V) ficava desativado sem cópia interna, então imagem/texto de outro programa não colava.
  Agora a ação acompanha a área de transferência do sistema (`_atualizar_colar`, sinal dataChanged). Conferido com
  a área de transferência real do Windows (bitmap).
- Versão 0.31.1. 550 testes passando.
- Correção de travamento: traçado de foto (~80 mil pontos) travava o programa — `Shape.shape()` fazia união booleana
  miolo + faixa (minutos). Acima de `objetos.COMPLEXO` (1500 pontos) a área de clique é a caixa e o desenho é sem
  antialiasing (~12x mais rápido). Medido: redesenho 1 s -> 0,08 s; arrastar ~0,05–0,2 s. Cursor de espera no traçado.
- Versão 0.31.2. 551 testes passando.
- **Plugin Colorir metal** (Ferramentas → Plugins; `plugins/colorir_metal`): 1) grade de teste potência × intervalo
  (padrão do anúncio: 25–55 % × 0,01–0,10 mm a 4000 mm/min, quadrados de 8 mm, rótulos gravados) gerada direto em
  G-code com camadas internas T… (não gasta as 30 camadas do projeto), com prévia e tempo; 2) foto da placa: dois
  cliques (centros dos quadrados dos cantos) leem a cor de cada quadrado -> paleta salva por material
  (AppData/colorir_metal/paletas.json); 3) colorir: escolher a cor (ou "mais próxima de…") passa as formas
  selecionadas para uma camada de Preenchimento com potência/intervalo/velocidade da cor (mesma cor = mesma
  camada). Paleta de referência lida da foto do anúncio (20 W, inox) — só ponto de partida.
- Versão 0.32.0. 555 testes passando.
- **Plugin Cilindros e copos** (`plugins/cilindros`): cilindro reto ou copo cônico (boca, base, altura) + faixa da
  arte -> circunferência no meio da arte, largura útil descontando alça e margens, N artes em volta (passo em mm e
  graus), distorção e variação de foco no cone (sugere calçar a base), molde em leque exato (arcos = voltas do topo e
  da base da arte). Botões: aplicar no rotativo (liga e usa o Ø do meio da arte), criar área de gravação com guias
  (C29, não grava) e criar o molde em leque (C01).
- Versão 0.33.0. 560 testes passando.
- **Salvamento automático no próprio arquivo** (padrão a cada 2 min; Configurações → Editor): grava o .rbl sem
  fechar grupo nem apagar o histórico (só marca "salvo"; Ctrl+Z continua). Projeto sem nome, grupo aberto ou opção
  desligada: cópia de recuperação em AppData/RedBlackLaser/autosave.
- **Continuar o último projeto** ao abrir o programa (`restaurar_sessao`, opção "abrir_ultimo"): se fechou sem salvar
  (queda/força), reabre a cópia de recuperação como "não salvo"; senão reabre o último arquivo. Projeto novo
  descartado ao fechar = começa limpo.
- Versão 0.34.0. 565 testes passando.
- **Cilindros e copos — 3D e 360°**: diâmetro do meio (perfil em parábola boca/meio/base; bolinha amarela arrastável
  no desenho de lado); prévia 3D ao vivo só com QPainter (`vista3d.py`: malha de revolução, luz, arte aplicada por
  ângulo do rotativo; esquerdo gira, direito/Shift move a arte, roda = zoom; 5 materiais); área de gravação 360°
  como o rotativo grava (X = altura da arte com a boca à esquerda, Y = volta inteira; arte girada 90° para a
  esquerda, topo para a boca; `arte.textura_360`); render realista no Blender instalado (Cycles na placa de vídeo
  OptiX/CUDA/HIP, mesma vista da prévia; `render.py` com o script embutido); parâmetros salvos por projeto (QSettings
  cilindros/proj/...).
- Versão 0.35.0. 569 testes passando.
- Cilindros (ajustes pedidos): giro da prévia e mover a arte acompanham o mouse (estavam invertidos); "Altura do
  meio" (parábola por boca/meio/base com o meio em qualquer altura, bolinha arrasta nas duas direções); base sempre
  editável (saiu "Base igual à boca"); grupo Aparência com material, cor do copo e cor da gravação (padrão por
  material: pintado/térmico = cinza metálico); render com estúdio (softboxes, fundo escuro, verniz na pintura,
  cores sRGB->linear).
- Versão 0.35.1. 570 testes passando.
- **Encaixar na caixa** (Organizar, botão direito, Ctrl+Alt+E): a 1ª peça clicada é a caixa; o resto da seleção
  (imagem, forma, texto, grupo, vários juntos) vai para dentro, centralizado, com margem: "caber" (proporcional,
  aumenta ou diminui), "manter o tamanho e só diminuir" ou "esticar" (deforma para preencher). Correção:
  `_sel_ordem` sem repetidos (a mesma peça podia receber a transformação duas vezes).
- Versão 0.36.0. 573 testes passando.
- Cilindros: perfil com VÁRIOS pontos (taças, garrafas, bojudos): tabela "mm da boca / Ø", + ponto / − ponto,
  arrastar no desenho (cima/baixo = altura, lados = diâmetro), duplo clique = novo ponto, botão direito = remover;
  curva monotônica por trecho (Fritsch–Butland, não passa dos pontos). Prévia 3D acompanha o projeto sozinha (mover,
  editar, desfazer: `undo_stack.indexChanged`; seleção no modo "selecionadas"). Giro vertical no sentido de
  arrastar (arrastar para baixo mostra a boca).
- Versão 0.36.1. 575 testes passando.
- Cilindros: luz da prévia 3D em coordenadas da câmera e luzes/fundo do render girando com a câmera — o lado que
  se olha (inclusive atrás) fica sempre iluminado (medido: mesmo brilho a 0/90/180/270°).
- Versão 0.36.2. 575 testes passando.
- Cilindros: arrastar a arte no 3D (botão direito/Shift) MOVE as peças na área de trabalho ao soltar (área 360°:
  em volta = Y, cima/baixo = X; um passo de desfazer; quem passa da borda volta pelo outro lado). Fora da área 360°
  continua só prévia, com aviso.
- Versão 0.36.3. 576 testes passando.
- Campos de número no programa todo: setinhas ▲▼ visíveis no tema escuro (PNG desenhado ao iniciar, botões com
  destaque/pressionado) e roda do mouse só muda o valor com o campo clicado (`theme.RodaSoComFoco`: sem foco, a roda
  vai para o painel de trás e o campo não pega o foco).
- Versão 0.36.4. 577 testes passando.
- Cilindros: Ctrl+Z / Ctrl+Y dentro da janela do plugin (medidas/aparência com histórico próprio + movimentos da
  arte pelo desfazer do projeto, na ordem certa); faixa vermelha da arte arrastável no desenho de lado e setas ↑↓
  (Shift = 10 mm) no desenho e no 3D, ←→ giram a arte no 3D; arte movida pelo 3D não sai da área 360° em X (altura do
  copo) — encosta na borda (em Y continua dando a volta).
- Versão 0.36.5. 578 testes passando.
- **Primeira conexão com a máquina real (2026-11-11)**: Windows sem driver do CH340 (USB 1A86:7523, erro 28) —
  usuário instalou o CH341SER da WCH -> COM4. Bug corrigido: `TransporteSerial._erro` comparava o código do erro pelo
  NÚMERO do Qt 5; no Qt 6 TimeoutError = 9 (antigo ResourceError), e a espera de 0 s sem dados derrubava a conexão.
  Agora compara pelo NOME e TimeoutError não é perda. Conexão somente leitura conferida na SCULPFUN S30 Pro Max:
  GRBL 1.1h (1.1h.20220925), opções V,15,128, $30=1000 (S 0–1000), $32=1 (modo laser), $130=400 / $131=410 (área
  400 × 410 mm), $110/$111=6000 mm/min, $120/$121=1000 mm/s², $22=0 (sem homing), $20=0, estado Idle em 0,0.
  Obs.: a porta só pode ser usada por um programa (fechar o LightBurn antes).
- Plugin Cilindros: ligações com o projeto por métodos (não lambdas) — o Qt desliga quando a janela some (antes
  davam erro "objeto já apagado" depois de fechar o plugin).
- Versão 0.36.6. 579 testes passando.
- **CONTROLE DA MÁQUINA (Etapas 14/15)**: conexão continua só leitura até o usuário clicar "Liberar controle" (aviso
  de segurança). Liberado: mover o cabeçote ($J= jog, laser nunca liga; passo/velocidade), ir à origem, Enquadrar
  (contorna a área do trabalho com jog, laser desligado; "a partir daqui" no modo posição atual), Definir origem
  (G10 L20 P1), Desbloquear ($X), Iniciar trabalho (confirmação com área/tempo/checklist; streaming por contagem de
  caracteres no buffer de 127 bytes; "Concluído" só quando a máquina volta a Idle; error:/ALARM durante o trabalho
  pausa na hora e não envia mais nada), Pausar/Retomar ("!"/"~"), Parar (reset 0x18, sempre disponível, apaga o
  laser). Comandos de controle numa lista fechada (regex); "$" dentro de trabalho é recusado. Testado no simulador
  (jog/enquadrar/trabalho/erro/pausa/parar e o painel inteiro). Air assist ainda não.
- Versão 0.37.0. 587 testes passando.
- Enquadrar travava ~30 s em projetos com imagem grande (gerava percurso + G-code inteiros só para achar o retângulo;
  475 mil trechos na aba do escorpião). Agora `caixa_do_trabalho` usa só a geometria das peças das camadas com Saída
  (instantâneo; conferido igual ao do percurso). Iniciar mostra cursor de espera enquanto gera.
- Versão 0.37.1. 587 testes passando.
- **Imagem reduzida gravava com intervalo errado** (grave): a grade do raster usava o tamanho ORIGINAL da imagem
  (ex.: colada a 335 mm e reduzida para 50 mm -> 3354 × 3283 pontos, linhas a 0,015 mm em vez de 0,1 mm: 6,7× mais
  linhas, muito mais lento e queimando demais). Agora usa o tamanho real na mesa (`percurso`, escala da
  transformação). Gerar o trabalho do escorpião: ~30 s -> 0,47 s. Difusão de erro reescrita (~1,7× mais rápida,
  resultado idêntico).
- **Rotativo ligado sem querer** fazia o cabeçote correr até o fundo (Y × 5,7 em chapa plana): o plugin Cilindros
  agora pergunta antes de ligar; painel Máquina mostra aviso vermelho com "Desligar rotativo"; a confirmação do
  Iniciar avisa quando o rotativo está ligado.
- Air assist: G-code liga M8 nas camadas com "Ar" e M9 nas sem / no fim (`gc.analisar` aceita M8/M9); botão
  Air assist no painel. Enquadrar com laser fraco (M4, padrão 1 %, máximo 5 %; aviso de óculos).
- Posição do cabeçote ao vivo na mesa (mira vermelha, preenchida com laser ligado; X/Y no painel; status a 4×/s;
  posição de trabalho = MPos − WCO).
- Sons (opção "Sons"): início, pausa, parado, fim e erro/alarme (WAV gerado, winsound assíncrono); o alarme logo
  depois do Parar não toca erro.
- Versão 0.38.0. 594 testes passando.
- Parar "travava tudo": reset no meio do movimento deixa o GRBL em ALARM:3 e todo jog é recusado (error:9). Agora,
  depois de um Parar do usuário, o alarme é desbloqueado sozinho ($X); alarme de outra origem continua travado e o
  painel avisa "MÁQUINA EM ALARME: clique em Desbloquear". Simulador passou a recusar $J em alarme (como o GRBL).
- Cabeçote "fora da mesa": "Posição atual" gravava G10 (origem) no controlador, que fica salvo. Agora desloca as
  coordenadas do próprio G-code (`gc.deslocar`), sem mexer no controlador; botão "Zerar origem" (G10 L2 P1 X0 Y0);
  Iniciar/Enquadrar avisam se o trabalho sai do curso $130/$131 contado a partir de onde a máquina foi ligada.
- Versão 0.38.1. 596 testes passando.
- **Referenciar (homing)** pelos fins de curso (esquerda e frente; a S30 já vem com $23=7, $25=3000, $27=2): botão
  "Referenciar (home)"; se $22=0, pergunta e grava $22=1 (lista fechada aceita só $22=0/1 e $20=0/1); depois do "ok"
  do $H (espera até 120 s), a referência vira o 0,0 do trabalho (G10 L20 P1 X0 Y0). Opção "Referenciar ao liberar o
  controle". Simulador: G10 L2/L20 com WCO (status mostra WCO quando muda ou não é zero).
- Potência ao vivo no painel (S e % que a máquina informa no status). Perfil continua M3 por padrão (M4 dinâmico
  recomendado para gravação — Configuração da máquina).
- Versão 0.39.0. 597 testes passando.
- Air assist fraco: a S30 tem ar "automático" (10–30 L/min) controlado pela placa; M8 só ia nas camadas com "Ar".
  Nova opção "Ar forte no trabalho todo" (padrão ligada): M8 antes do primeiro movimento e M9 só no fim
  (`gc.ar_no_trabalho_todo`). Hipótese a confirmar na máquina: botão Air assist (M8) deixa a bomba forte.
- Versão 0.39.1. 597 testes passando.
- Rotativo com motor no eixo X ou Y (`Rotativo.eixo`): o desenho não muda; com X, a volta sai no X e o comprimento
  da peça no Y (limite da mesa passa a valer no Y).
- Duplo clique na mesa (sem objeto, sem ferramenta) leva o cabeçote até o ponto, laser desligado, só com controle
  liberado e dentro da mesa/curso (`laser_ate_ponto`).
- Versão 0.39.2. 599 testes passando.
- Imagem (modo Imagem) passa a respeitar "Ângulo de varredura" 90° (varre a imagem girada e devolve ao lugar);
  outros ângulos em imagem continuam 0°. Duplo clique na mesa avisa na barra quando falta conectar/liberar controle.
- Versão 0.39.3. 600 testes passando.
- Linha com medida digitada: com a linha em andamento, aponta o mouse e digita o número (vírgula ok) + Enter = o
  próximo ponto fica exatamente a essa distância na direção do mouse (Shift = 45°). Backspace corrige, Esc cancela
  o número, Enter sem número termina a linha.
- Versão 0.39.4. 601 testes passando.
- Medida digitada: Enter = no esquadro (eixo mais perto do mouse); Shift+Enter = ângulo livre do mouse.
- Versão 0.39.5. 601 testes passando.
- Prévia de desenho (linha/forma em andamento): azul-escuro #0b3fb3, 2 px, na mesa clara; amarelo só no tema escuro.
- Versão 0.39.6. 601 testes passando.
- Arrastar e soltar (`soltar`): .rbl abre (pergunta se salva o atual); SVG/DXF/PDF/AI/PNG/JPG entram centrados
  onde foram soltos na mesa (fora da mesa: posição normal da importação); imagem/SVG/texto arrastados de navegador
  usam o mesmo caminho do colar. Tipo não suportado avisa.
- Versão 0.39.7. 602 testes passando.
- Linha: guias de alinhamento (`_alinhar_linha`) — mouse na mesma vertical/horizontal de um ponto da linha ou de
  canto de objeto (raio do encaixe, mesmo longe) gruda e mostra guia tracejada; Alt desliga; Shift (45°) só um eixo.
- Versão 0.39.7 (sem publicar antes). 603 testes passando.
- Auditoria: nenhuma ação/método sem acesso na interface (varredura de QAction fora de menus/barras/contexto e de
  métodos públicos sem chamada). "Juntar pontas" (Alt+J), Fechar caminho e Otimizar também no menu Ferramentas e
  no botão direito. Desempenho: alvos de encaixe em cache enquanto desenha (24 → 4,5 ms por movimento com 400
  objetos). Bug: Enquadrar com rotativo agora usa a mesma escala/eixo do G-code; checagem de curso ignora o eixo
  que gira. Teste F4 com diagnóstico (instável raro na suíte completa).
- Versão 0.39.8. 604 testes passando.
- Barra da esquerda: Juntar pontas, Fechar caminho, Eliminar duplicados, Inverter direção e Otimizar, com ícones
  próprios e dicas animadas (demo_juntar/fechar/duplicados/inverter/otimizar).
- Bug (causa do teste F4 "instável"): menus Organizar, Produção, Janela e Ajuda não tinham referência no Python e a
  coleta de lixo podia apagá-los da barra de menus; agora ficam em `_menus_vivos`. Pesquisa F4 também mantém as
  ações vivas durante a coleta (id() reaproveitado pulava comandos).
- Versão 0.39.9. 604 testes passando (2 rodadas completas seguidas).
- Mira do cabeçote suave: status a cada 0,12 s (era 0,25) e a mira desliza entre leituras (timer 16 ms,
  `definir_cabecote`/`cabecote_alvo`). Durante o trabalho a mira é mapeada de volta ao desenho
  (`_mapa_saida_para_desenho`: desfaz o deslocamento da "posição atual" e a escala/troca de eixo do rotativo).
  Bug: com rotativo, "posição atual" e a conferência de curso usavam a caixa sem escala; agora `_caixa_na_saida`.
- Versão 0.40.0. 605 testes passando.
- Tempo estimado acima das camadas: aba aberta e projeto inteiro (todas as abas), calculado numa thread 1,5 s
  depois de cada mudança (`_agendar_tempo`/`_calcular_tempo`/`tempos_estimados`); tela não trava (pior caso 75 ms
  com imagem de 1 h).
- Plugin Orçamento (`plugins/orcamento`): tempo da aba/projeto/manual × valor da hora (padrão R$ 30,00, salvo),
  material, outros, margem %, quantidade; copiar orçamento. Incluído no gerar.ps1.
- Versão 0.41.0. 607 testes passando.
- "Ver peças cortadas em MDF (renderizar)…" (Ferramentas; `ui/render_mdf.py`): textura procedural de MDF/branco/
  compensado/acrílico, bordas queimadas, sombra, furos vazados, gravação como queimado e linha fraca como risco.
  Corte = Linha com potência×passadas/(mm/s) ≥ 3. `montar_pecas`: contorno em volta de tudo vira chapa/sobra
  (auto/forçado), peças sólidas com furos diretos. Salvar PNG a 8 px/mm.
- Versão 0.42.0. 609 testes passando.
- Prévia MDF: corte = Linha com potência ≥ 40 % (nome com grav/marc/risc/cola/refer = marcação); o porta-retrato
  (100 % a 6000 mm/min) saía só como risco escuro no fundo escuro — fundo agora claro. Render 3D no Blender
  (`preparar_3d`/`SCRIPT_3D`): peças extrudadas com a espessura (lida do nome do arquivo, ex. "3mm"), topo com a
  textura/gravações, laterais queimadas, mesa, 3 luzes, Cycles na GPU (~9 s OptiX).
- Versão 0.42.1. 609 testes passando.
- Janela da prévia MDF/3D: Ajustar à janela (Ctrl+0), −/+ (Ctrl+rodinha, Ctrl+/−), 100 %, tela cheia (F11; Esc
  sai); imagem reajusta ao redimensionar.
- Versão 0.42.2. 609 testes passando.
- Prévia MDF: contornos feitos de pedaços abertos (ex.: "Formas associadas" do Juntar com 2 trechos) são
  encadeados (`encadear`); aberturas de 0,1–10 mm são fechadas na prévia mas AVISADAS (peça fica presa no laser).
  3D: anéis passam por `simplified()` antes do Blender (cruzamento quebrava o preenchimento). Pontas a ≤ 0,1 mm =
  fechado; peças erguidas 0,05 mm da mesa.
- Versão 0.42.3. 610 testes passando.
- Aparar: linha que só ENCOSTA (ponta a ≤ 0,2 mm do contorno, junta em "T") e linha que termina em cima de si
  mesma também dividem o contorno. Antes, sem cruzamento, o contorno inteiro sumia (coração do porta-retrato).
- Versão 0.42.4. 611 testes passando.
- 3D com abas empilhadas ("Montar todas as abas"): 1ª aba por cima, material pelo nome da aba (rosa/branca…),
  `_camada_3d` + SCRIPT_3D com várias camadas (z0). Material "MDF rosa". `importar_pdf.load(caminho, pagina_n)`.
- Projeto F:\Downloads\porta_retrato_vallentina_hellena_ornamentado.rbl do PDF 1:1 do usuário (págs. 3–5: frente
  branca + base, camada rosa, tampa traseira centralizada nas janelas) + render 3D empilhado (_3D.png).
- Versão 0.43.0. 611 testes passando.
- Bancada padrão da RedBlack: 365 de largura × 370 de altura (MAQUINA_PADRAO, geometria.BED_*, MCP) e gravada nas
  configurações do usuário. Testes fixam a mesa 400 × 400 deles em tests/mesa_dos_testes.py.
- Versão 0.43.1. 612 testes passando.
- Retomar trabalho interrompido (queda de luz/reset/Parar): linhas enviadas + progresso gravados em disco
  (trabalho_em_andamento/, a cada 1 s); botão "Retomar interrompido…" volta N linhas (padrão 40, cobre o buffer) e
  recria o estado com `gc.retomar_de` (G21/G90, ar, M3/M4 S, F, G0 até o ponto com laser apagado). Avisa para
  referenciar antes (sem homing o 0,0 muda).
- "Iniciar a partir de…": escolhe início/fim em linhas, trecho destacado no desenho, mesma restauração de estado.
- Mira contínua (luz fraca parada, M3 S≤2 % + G1 F1000; M5 desliga) e "Soltar motores" ($1=25 / $1=255).
- Versão 0.44.0. 615 testes passando.
- Orçamento v2 (`orcar`/`dicas`): MDF = chapa ÷ placas × camadas (35 placas = 11 peças de 3 camadas), máquina,
  trabalho manual (tempo × sua hora), insumos, custos fixos do pedido; custo, preço de venda e lucro separados
  (peça e pedido); "confirmado" por valor (resto aparece como ESTIMATIVA); avisa dados faltando; dicas de margem;
  copiar para o cliente (só preço) e interno.
- Versão 0.44.1. 616 testes passando.
- Orçamento v3 com os dados do levantamento do usuário (chapa R$ 44 / 35 placas, tinta R$ 46 / 900 ml, cola
  R$ 39 / ~35 peças, laser R$ 50/h de referência, mão de obra R$ 15/h; modelos Tyfani e Valentina Hellena):
  desembolso × mão de obra × remuneração da máquina × lucro separados, custo operacional real do laser à parte,
  tabela 1/5/10/20+ com desconto, modelos salvos, dados confirmados × estimativas.
- Versão 0.44.2. 616 testes passando.
- Orçamento em 2 abas: "Orçamento" (cliente, produto, tempo de laser puxado do plano aberto por padrão, cartões
  preço/total/lucro/fica, tabela item a item com confirmado × estimativa, tabela por quantidade com desconto
  aplicado) e "Configurações" (materiais, horas, margem, descontos editáveis, empresa: nome, slogan, contatos, logo,
  cor, validade, prazo, observações). "Gerar PDF" A4 com a marca (QPdfWriter, sem custos internos).
- Versão 0.45.0. 616 testes passando.
- Prévia MDF: contorno externo só vira "chapa" se for quase retangular (área ≥ 90 % da caixa); frentes com nomes
  (Nathan/Isabella) eram tratadas como chapa. Projeto da cliente Carine (Nathan & Isabella, 6 mm + 3 mm) na pasta
  da rede.
- Versão 0.45.1. 616 testes passando.
- Orçamento: produto "📐 Plano aberto: <arquivo>" (tempo do plano, preço pela margem); modelos salvos usam o
  PRÓPRIO tempo (antes o Tyfani pegava os 224 min do projeto da Carine → custo R$ 196 com preço R$ 60). Aviso em
  vermelho quando o preço fica abaixo do custo. `--orcamento` abre o programa direto no orçamento.
  Projeto Carine: 6 mm 300 mm/min 2 passadas, 3 mm 600 mm/min 1 passada (valores típicos 20 W, a testar).
- Versão 0.45.2. 616 testes passando.
- Materiais: predefinição RedBlack "MDF 3 mm corte 300 mm/min 80 % 2 passadas, ar" (`mt.PREDEFINIDOS_REDBLACK`,
  vale em qualquer PC; um material seu igual substitui) e botão "Editar…" (vira material seu). Aplicado na camada
  3 mm do projeto da Carine.
- Versão 0.45.3. 617 testes passando.
- Geradores de teste (observados no LaserGRBL 7.14: PowerVsSpeed, CuttingTest, ShakeTest/precisão — só nomes de
  campos, sem código): matriz com tipos prontos (Potência×Velocidade, Corte Velocidade×Passadas com potência fixa,
  Potência×Passadas, Potência×Intervalo), colunas = potência ou velocidade, modo do laser M3/M4 por teste, botão
  "Enviar para a máquina" (`enviar_teste`: confirmação, Posição atual, curso). Teste de precisão (quadrado, círculo,
  diagonais, régua de 10 mm) em Laser → Teste de precisão.
- Versão 0.46.0. 620 testes passando.
- Barras com grupos (`_agrupar_barras`/GRUPOS_BARRA): Formas, Aparar e bolear, Deslocar e booleanas, Matrizes,
  Contornos, Arquivo, Zoom, Configurações, Agrupar, Espelhar, Alinhar, Distribuir — clique usa o último, clique e
  segure (ou botão direito) troca; o escolhido fica salvo. Ferramentas 26→11 botões, Principal 40→20. Ícones 18–22 px
  conforme a altura da tela. Menu Organizar de 55 itens para 15 (submenus por assunto). F4 também procura na
  descrição (dica) dos comandos e nos grupos das barras.
- Versão 0.47.0. 620 testes passando.
- Investigação corte X×Y: $100/$101, $110/$111, $120/$121 iguais (lidos do LaserGRBL); $30=1000, $32=1. Diferenças de
  software: RedBlack em M4 a 80 % × LaserGRBL M3 a 100 %. Causa raiz provável: feixe do diodo não é redondo (X mais
  largo). Correção: perfil `corte_m3` (padrão ligado) — com perfil M4, camadas em Linha saem em M3; gravação segue M4.
- Painel direito: Camadas 60 % / Máquina 40 %, largura 430 px, coluna do nome da camada estica; LAYOUT_VERSAO 4.
- Versão 0.47.1. 621 testes passando.
- Painel lateral: largura medida pelo conteúdo na tela real (`_garantir_largura_docks`), nunca mais estreito que o
  necessário (o 430 px fixo cortava tabela e botões); LAYOUT_VERSAO 5.
- Calibração de corte X/Y (Laser → Calibração de corte X/Y…, desligada por padrão): `gc.definir_fator_x` muda só a
  velocidade dos trechos de CORTE conforme a direção (X = vel_x/vel_y, Y = 100 %, diagonais/curvas por cos² com
  direção suavizada em ~2 mm, degraus de 10 mm/min); nunca acelera, S/geometria iguais, nada gravado no GRBL.
  Perfis por material (inicial MDF 3 mm: X 700 / Y 800, 85 %, 2 passadas), ativar/desativar/restaurar, teste
  SEM × COM (quadrado + linhas H/V), aviso de diferença grande (< 70 %), estado na barra de status.
- Versão 0.48.0. 623 testes passando.
- Compensação do eixo X (substitui o fator %): `gc.definir_comp_x(desconto, minimo)` desconta mm/min fixos nos
  CORTES em X (padrão 250, medido: Y 800 / X 550 em MDF 3 mm), gradual por cos² com direção suavizada e peso em
  degraus de 5 %, nunca abaixo do mínimo (padrão 150; camada já mais lenta fica igual), nunca acima do programado.
  LIGADA por padrão e salva (QSettings "compensacao_x"); menu Laser → "Compensação do eixo X ligada" + janela
  (desconto, mínimo, restaurar padrão, teste SEM × COM). Tempo estimado do percurso considera a compensação.
- Versão 0.49.0. 624 testes passando.
- Orçamento simplificado: uma linha só de máquina (hora de máquina R$ 50, sem "custo operacional" separado), sem o
  cartão "Fica para você"; cliente com contato, descrição para o cliente, PIX/forma de pagamento. PDF refeito a
  300 dpi (fonte com espaçamento certo): número, emissão e validade, cartões Para/Produto, imagem do projeto
  (render MDF), tabela, TOTAL em destaque, valores por quantidade, condições, pagamento, "Aprovado por".
- Versão 0.49.1.
- Setas do teclado movem o cabeçote depois de clicar num botão de mover (painel Máquina): toque = 10 mm, Alt 0,1,
  Ctrl 1, Shift 50; segurar (> 350 ms) = jog longo até o fim do curso/mesa, soltar (ou perder o foco) cancela (0x85).
- Versão 0.50.0. 625 testes passando.
- Projetos de exemplo (tools/projetos): carroça colonial (35 peças em MDF 3 mm redesenhadas do PDF que só tinha
  imagem; assoalho com recortes para os braços dos berços) e porta-retrato Isabella e Nathan (vetores 1:1 do PDF,
  camadas pela profundidade; base de 6 mm em 3 partes, apoios de 6 mm e corações dentro das sobras das janelas).
- README novo (capturas em docs/img); referência completa movida para docs/GUIA.md. 632 testes passando.
- Regras para projetos criados: corte 800 mm/min, potência máx. 85 % (nunca 100 %); encaixes SEM folga (rasgo =
  soma das espessuras). Carroça: furos Ø4 (= vareta), abas 3 mm. Porta-retrato todo em MDF 3 mm: rasgos da base
  26 × 9 (3 + 3 + 3), base em 3 camadas de 3 mm, 4 triângulos de apoio.
- tools/projetos/etiquetas.py: grava o código de cada peça dentro dela (lugar livre mais central, longe de furos e
  linhas; gira junto com a peça), camada C09 15 %/3000 mm/min antes dos cortes + aba "SÓ LETRAS" para chapa já
  cortada. tools/projetos/carroca_manual.py: manual de montagem em PDF (lista de peças, mapa da chapa, assoalho como
  mapa dos rasgos, passo a passo, vistas lateral e de frente, meio-encaixe). O gerador da carroça já sai com letras.
- Manuais: porta-retrato (base laminada, encaixe, apoios) e gabarito 1:1 das laterais da carroça. Corações do
  porta-retrato unidos numa peça de 3 mm (divisas gravadas fracas).
- Versão 0.51.0. Predefinições de corte RedBlack: MDF 3 mm = 650 mm/min, 85 %, 2 passadas; MDF 6 mm = 600 mm/min,
  85 %, 5 passadas (`materiais.corte_mdf`, usado pelos geradores de projeto).

## Concluído antes
- Etapa 12 — simulador GRBL (aprovada em 2026-11-07).
- Etapa 11 — G-code vetorial (aprovada em 2026-11-07).
- Etapa 10 — prévia do percurso (aprovada em 2026-11-07).
- Etapa 9 — camadas e parâmetros (aprovada em 2026-11-07).
- Etapa 8 — formas e edição vetorial (aprovada em 2026-11-07).
- Etapa 7 — texto e fontes (aprovada em 2026-11-07).
- Etapa 6 — importar PNG/JPG (aprovada em 2026-11-07).
- Etapa 5 — importar SVG (aprovada em 2026-11-07).
- Etapa 4 — desfazer/refazer e projeto (aprovada em 2026-11-07).
- Etapa 3 — objetos (aprovada em 2026-11-07).
- Etapa 2 — área gráfica (aprovada em 2026-11-07).
- Etapa 1 — interface (aprovada em 2026-11-07).

## 0.52.0 — laser ligado forte, varredura em Y, ar confirmado pela máquina
- Painel Máquina: botão "🔥 Laser ligado" com potência até 100 % (pede confirmação; M3 S… + G1 F sem eixos).
  Com ele aceso, as setas do teclado movem o cabeçote ($J herda o M3) e o laser risca. Mira e laser: um só por vez;
  apagam ao iniciar trabalho ou travar o controle.
- "Ar na máquina: FORTE/fraco": lê o campo A: (F = M8 ativo) do relatório de status do GRBL. Na S30 o ar fraco é a
  bomba no modo baixo (relé do M8 desligado); se aparecer FORTE e sair pouco ar, é o regulador da bomba/mangueira.
  Simulador agora guarda o M8 e informa Ov:/A:F.
- Camada: caixa "↕ Varrer no eixo Y (linhas verticais)" = ângulo de varredura 90° (preenchimento e imagem).

## 0.52.1 — fim dos pontinhos/furinhos (envio do trabalho)
- O "ok" do GRBL agora manda a próxima linha NA HORA (readyRead da serial → `Conexao.tick(0)`), sem esperar o
  relógio de 50 ms da tela. Antes, nos trechos curtos (curvas, linhas de gravação) o buffer de 127 bytes esvaziava, a
  máquina parava a cada linha e o laser marcava pontinhos (M4) e furinhos (M3, corte).
