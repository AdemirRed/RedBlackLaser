# Guia de uso do RedBlack Laser

Referência completa das funções, atalhos e fluxos. Visão geral e instalação: [README](../README.md).

## Encaixe em cantos e pontos (`F9`)
Ligado por padrão. Medir, formas, linhas, texto e nós grudam em cantos, centros, cantos da mesa e no
ponto inicial da linha (clicar nele fecha o contorno). Uma marca amarela mostra onde vai encaixar.
Segure Alt para desligar na hora.

## Texto variável (nomes, números de série, data)
No diálogo de texto marque "Texto variável" e use `{Nome}` (coluna da planilha), `{n}` / `{n:3}`
(número de série), `{data}`, `{hora}`. No painel Texto variável: carregar a planilha CSV (Excel → "CSV"),
escolher a linha, ajustar o contador e "Exportar G-code em lote" (um arquivo por peça, sem sobrescrever).
A planilha fica guardada dentro do projeto.

## Forma com medidas exatas (`Ctrl+Shift+F`, menu Ferramentas)
Círculo por **diâmetro ou raio** (ex.: Ø99,60), elipse, retângulo (com raio dos cantos) e polígono, com centro
X/Y exato e camada. Depois de criada, Largura/Altura na barra também ajustam a medida.

## Ferramentas novas (paridade com o programa de referência)
| Função | Onde / atalho |
|---|---|
| Deslocar formas (offset) | Ferramentas, Alt+O |
| Solda, união, subtrair, interseção | Ferramentas: Ctrl+W, Alt++, Alt+-, Alt+* (subtrair: da 1ª clicada) |
| Cortar formas (cortador) | Ferramentas, Alt+Shift+C — a última clicada corta as outras |
| Tesoura (aparar) | Ferramentas, Ctrl+K — clique no trecho entre cruzamentos (fica vermelho antes) |
| Matriz em grade / circular | Organizar |
| Encostar, mover para a página, distribuir espaçado, mesma largura/altura | Organizar |
| Espelhar ao longo da linha | Organizar, Ctrl+Shift+M — a linha é a última clicada |
| Bloquear / desbloquear | Organizar |
| Mover / Tamanho / Girar ligados ou não | botões ● na barra de status |
| Recortar, colar no lugar, inverter seleção, selecionar formas, fechar caminho, eliminar duplicados | Editar |
| Ângulo de varredura, bidirecional, hachura cruzada, sobrevarredura | painel Camadas (modo Preenchimento) |
| Ações em todas as camadas | clique direito na tabela de camadas |
| Configurações | Editar → Configurações (cópia automática, setas, encaixe, zoom, texto, otimização) |
| Teclas de atalho | Editar → Teclas de atalho… (procura, avisa repetidas, lembra) |
| Histórico de anulações | Editar → Histórico (clique num passo para voltar até ele) |
| Escala em % | campos Escala L / Escala A na barra de propriedades |
| Exportar SVG / DXF, importar DXF | Arquivo |
| Guias (pontes), sobrecorte | painel Camadas (modo Linha) |
| Preencher todas as formas de uma vez | painel Camadas (modo Preenchimento) |
| Gravar imagens: pontilhado, limiar, tons de cinza, negativo | painel Camadas (modo Imagem) |
| Editar nós por teclas | Editar nós + cursor sobre o nó/trecho: D exclui, I insere, M meio, L reta, C canto, B quebra |
| Copiar ao longo do caminho, cisalhar, contorno elástico | Organizar |
| Código QR | Ferramentas → Desenhar forma → Criar código QR… |
| Código de barras EAN-13 | Ferramentas → Desenhar forma → Criar código de barras EAN-13… |
| Notas do projeto | Arquivo → Mostrar notas (Ctrl+Alt+N) — salvas dentro do projeto |
| Associar formas (juntar linhas soltas, ex.: DXF) | Editar → Associar formas selecionadas (Alt+J) |
| Imprimir em escala 1:1 | Arquivo → Imprimir (Ctrl+P preto, Ctrl+Shift+P com cores) |
| Ajustar zoom à seleção | Janela (Ctrl+Shift+0) |
| Autoagrupar | Organizar — cada contorno externo vira grupo com o que está dentro |
| Otimizar formas (menos nós) | Editar (Alt+Shift+O) |
| Paleta | 30 camadas (C00–C29) |
| Rotativo (rolo/mandril) | Laser → Configuração do rotativo… — aviso vermelho "ROTATIVO" quando ativo; calibre na máquina |
| Teste de intervalo / passadas | Laser → Matriz de testes… → "As linhas variam" |
| Traçar imagem (vetorizar) | Editar → Traçar imagem… (Alt+T), com a imagem selecionada |
| Texto ao longo do caminho | Editar → Aplicar caminho ao texto… (texto + caminho clicado por último) |
| Converter em bitmap | Editar → Converter em bitmap (Ctrl+Shift+B) |
| Brilho / contraste / gama da imagem | painel Camadas (modo Imagem) |
| Modelos de projeto | Arquivo → Salvar como modelo… / Novo a partir de modelo |
| Exportar / importar preferências | Arquivo |
| Remover linhas sobrepostas, encaixe na grade | Editar → Configurações |
| Propriedades do texto | barra "Texto" (fonte, altura, negrito, itálico, alinhamento, entrelinha) |

## Compensação de kerf (painel Camadas → Kerf)
Meça a largura que o feixe remove (ex.: corte um quadrado de 20 mm e meça: k = 20 − medida) e digite em
"Kerf" da camada (modo Linha). No G-code e na prévia, peças crescem k/2 e furos diminuem k/2; o desenho
continua na medida nominal. Linhas abertas e camadas de preenchimento não são compensadas.

Abrir um projeto direto: `python -m redblack caminho\projeto.rbl`.

## Frisos para dobra (Produção → Frisos para dobra…)
Painel com rebaixos paralelos para curvar MDF (kerf bending): comprimento, altura, quantidade, largura do
friso, margem. Opção de calcular o comprimento pelo diâmetro: L = π × (Di + 2t − e). Cria o contorno (corte)
e os frisos (camada em Preenchimento, que sai antes do contorno). A profundidade depende da calibração.

## Gabarito e produção em lote na mesa (menu Produção)
1. Produção → **Gabarito na mesa…**: colunas, linhas, tamanho da célula, vão e posição (ou "Célula do
   tamanho da seleção" / "Centralizar na mesa"). Gabaritos podem ser salvos com nome para reutilizar.
2. Selecione o desenho (ex.: placa com `{Nome}`) → **Preencher gabarito com a seleção**: uma cópia
   centrada em cada célula; a peça 1 usa a linha atual da planilha, a peça 2 a seguinte, e assim por diante.
3. **Próxima mesa** avança todas as peças de uma vez. "Exportar G-code em lote" gera um arquivo por mesa.
Peças sem linha na planilha (última mesa incompleta) aparecem com "—" e **não vão para o G-code**.
O gabarito é só guia na tela (tracejado azul numerado); não é cortado.

Girar peças: campo "Girar peças na célula" no gabarito (ex.: 90° para peças deitadas em células em pé);
o encaixe na célula considera a peça já girada.

## Materiais (painel Materiais)
Lista para a SCULPFUN S30 Pro Max 20 W (compensado, tília, paulownia/cortiça, acrílico preto, MDF, aço inox,
papel kraft, couro). Escolha o material, selecione a camada e "Aplicar à camada" (desfazível). Os valores são
**referência de revendedor, não validados**: teste numa sobra. Depois do teste, "Salvar camada como
material…" cria o seu preset ([Meu]), que fica no topo da lista.

## Matriz de testes de materiais (Laser → Matriz de testes…, ou painel Materiais)
Gera um G-code com uma grade de quadrados: cada coluna com uma potência, cada linha com uma velocidade, com
os valores gravados ao lado. "Faixa em volta do material selecionado" monta a grade em torno do preset
escolhido. Grave numa sobra do material e depois use Materiais → **Salvar do quadrado escolhido…** (ou
Laser → Salvar material do quadrado escolhido…): clique no quadrado que ficou melhor, dê nome e espessura.
A última matriz é lembrada entre sessões; "Abrir outra matriz (.gcode)…" lê os parâmetros guardados no
próprio arquivo. Nada é enviado à máquina; o projeto não é alterado.

## Digitar a medida na tela
- Clique no valor da largura (abaixo da seleção) ou da altura (à direita) e digite a medida; Enter aplica,
  Tab passa para a outra medida, Esc cancela. "Manter proporção" vale aqui também.
- Com um objeto selecionado, comece a digitar um número: abre a largura já com o que foi digitado.

## Âncoras (Organizar → Prender à âncora, `Ctrl+Shift+A`)
Clique no objeto pai, depois Shift+clique nos que vão junto e `Ctrl+Shift+A`. Arrastar, girar ou
redimensionar o pai leva os presos; cada preso continua se movendo sozinho. Linhas tracejadas mostram as
ligações; na lista Objetos, os presos têm o ícone de âncora. Organizar → Soltar da âncora desfaz a ligação.
Renomear objeto: duplo clique na lista Objetos ou `F2`.

## Mostrar medidas (`F10`)
Medir mostra o comprimento em cima da linha; linhas em desenho mostram o segmento atual; seleção e formas
em desenho mostram largura (abaixo) e altura (à direita). F10 ou o botão da barra liga/desliga; a escolha
fica guardada.

## Arquivos recentes
Arquivo → Abrir recente: os 8 últimos projetos abertos ou salvos.

## Formas
| Ferramenta | Como |
|---|---|
| Retângulo `Ctrl+R` / Elipse `Ctrl+E` | arrastar; Shift = quadrado/círculo; Ctrl = do centro |
| Polígono | arrastar do centro ao vértice; "Lados" na barra de propriedades |
| Linhas `Ctrl+L` | clicar pontos; clicar no 1º fecha; duplo clique/Enter termina; Shift = 45° |
| Editar nós ``Ctrl+` `` | arrastar os pontos de um caminho selecionado |
| Agrupar `Ctrl+G` / Desagrupar ou separar `Ctrl+U` | menu Organizar; separar = um objeto por contorno (ex.: frisos) |
| Ordem de corte | lista Objetos (de cima para baixo, dentro de cada camada): ▲ ▼ ⤒ ⤓, PgUp/PgDown, Ctrl+PgUp/PgDown |
| Duplicar `Ctrl+D` | cópia no mesmo lugar, já selecionada para mover |
| Cantos arredondados | campo "Raio" na barra: novos retângulos já saem arredondados; Organizar → Arredondar cantos aplica à seleção |

## Conectar à máquina (somente leitura)
Painel Máquina → Procurar portas → escolher a porta (ou "Simulador") → Conectar. O programa só lê
identificação, configurações (`$$`) e estado; não move, não liga o laser e não desbloqueia alarmes.
"Salvar relatório da máquina…" grava os valores lidos em JSON.

## Simular um G-code (sem máquina)
```powershell
python tools\simular.py arquivo.gcode            # relatório: ok/erros/alarmes, estado, tempo, mm com laser
python tools\simular.py arquivo.gcode --limites  # liga limites por software (400 × 400 mm)
```
Usa um controlador GRBL simulado em memória; nada é enviado a nenhuma porta.

## Exportar G-code (`Ctrl+Shift+G`)
Gera um arquivo GRBL (mm, absoluto, M3, S 0–1000) a partir do percurso. Recusa e não grava nada se
algo sair da área. **Perfil da máquina NÃO confirmado**: não execute sem conferir (docs/MAQUINA.md).
Nada é enviado à máquina pelo programa.

## Prévia do percurso (`Alt+P`)
Mostra, sem enviar nada à máquina, o que o laser faria: cortes na cor da camada, deslocamentos sem
laser tracejados e a cabeça do laser (cheia = emitindo). Resumo por camada, estimativa de tempo
**mínima** (ignora aceleração) e simulação com controle deslizante. A velocidade de deslocamento
(6000 mm/min) é uma suposição editável.

## Camadas
Clique numa cor da paleta inferior para colocar a seleção naquela camada. No painel Camadas:
Saída (vai para o laser), Exibir (só tela), ▲/▼ (ordem de saída) e os parâmetros da camada
selecionada. Velocidade em mm/min. **Valores padrão não são validados para máquina/material.**

## Texto (`T`)
Clique na área de desenho para criar; duplo clique num texto para editar. Altura = altura do X
maiúsculo em mm. `Ctrl+Shift+C` converte em curvas. Projetos guardam o contorno: abrem iguais
mesmo sem a fonte instalada (com aviso).

## Importar imagens (`Ctrl+I`)
PNG e JPG entram no tamanho físico do DPI gravado no arquivo; sem DPI, 96 dpi com aviso.
A orientação de fotos de celular (EXIF) é aplicada. O arquivo original fica guardado dentro do projeto.

## Importar SVG (`Ctrl+I`)
Suporta path, rect, circle, ellipse, line, polyline, polygon e grupos, com unidades (mm, cm, in,
pt, pc, px a 96/pol), viewBox e transformações. Texto, imagens, `use` e outros elementos não são
importados e aparecem num relatório. Arquivo de exemplo: `docs/exemplos/amostra.svg`.

## Projeto e histórico

| Ação | Atalho |
|---|---|
| Novo / Abrir / Salvar / Salvar como | `Ctrl+N` / `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` |
| Desfazer / Refazer | `Ctrl+Z` / `Ctrl+Y` ou `Ctrl+Shift+Z` |

Projetos são arquivos `.rbl` (JSON legível, mm). O título mostra `*` quando há alterações não salvas.

## Edição de objetos

| Ação | Como |
|---|---|
| Selecionar | clique; Shift+clique adiciona/remove; arrastar no vazio; `Ctrl+A`; `Esc` limpa |
| Mover | arrastar o objeto; setas (1 mm), Shift+setas (10 mm); ou campos X/Y |
| Redimensionar | alças de canto (proporção; Shift livre), alças de lado; ou Largura/Altura |
| Girar | alça redonda acima da caixa (Shift: 15°); campo Girar (positivo = horário) |
| Ponto de referência | seletor de 9 pontos à esquerda de X |
| Alinhar/distribuir/espelhar | menu Organizar |

## Navegação na área de desenho

| Ação | Como |
|---|---|
| Zoom no ponto do cursor | roda do mouse |
| Zoom | `+` / `-` (área focada), `Ctrl++` / `Ctrl+-`, botões da barra |
| Ver a mesa inteira | `Ctrl+0` ou botão "Ajustar à mesa" |
| Deslocar | botão do meio arrastando, ou `Espaço` + botão esquerdo |
| Medir | ferramenta Medir (`M`), arrastar; `Esc` encerra |

## Requisitos

- Windows 10/11 x64 (testado: Windows 10 Pro 19045)
- Python 3.10+
- PySide6 (testado 6.11.1): `python -m pip install -r requirements.txt`

## Executar

```powershell
cd C:\Users\RedBlack-PC\source\repos\RedBlackLaser
python -m redblack
```

## Verificar

```powershell
python -m unittest discover -s tests        # testes da interface (sem tela, offscreen)
python tools\capturar.py <pasta>            # gera capturas 1600x900 e 1024x640
```
