# Comparativo: LightBurn × RedBlack Laser (2026-11-08)

Base: menus, diálogos e os 7 084 textos da interface do LightBurn (pt-BR) levantados com REA em
`Documentos\RedBlack_referencia_LightBurn\`, conferidos contra o código atual do RedBlack (427 testes).
Substitui as tabelas do início do dia em `PLANO_PARIDADE_LIGHTBURN.md`.

Legenda: ✅ tem · 🟡 parcial · ⬜ falta. "Máquina" = precisa da SCULPFUN conectada para fazer e validar.

## Resumo
| Área | Situação |
|---|---|
| Desenho e edição vetorial | ✅ praticamente completa |
| Organizar (alinhar, matrizes, guias inteligentes, disposição automática) | ✅ completa |
| Texto | ✅ completa |
| Camadas e parâmetros de corte/gravação | ✅ completa (inclui subcamadas) |
| Imagens (gravação, ajuste, vetorizar) | ✅, menos máscara/recorte |
| Arquivos | 🟡 falta HPGL/Gerber |
| Controle da máquina (enviar, enquadrar, mover) | ⬜ bloqueado: máquina ainda não chegou |
| Câmera, galvo, LiDAR, Wi-Fi | ⬜ fora do escopo da S30 |

## O que já temos igual ao LightBurn
- **Arquivo**: novo, abrir, salvar, recentes, modelos, importar SVG/DXF/**PDF/AI**/PNG/JPG (centralizar e
  agrupar ao importar), exportar SVG/DXF/G-code, imprimir 1:1, exportar/importar preferências, notas do projeto, **páginas** (abas com adicionar/duplicar/excluir).
- **Editar**: desfazer/refazer com histórico, recortar/copiar/colar/colar no lugar/duplicar, inverter
  seleção, selecionar formas (abertas, da camada, contidas, menores, círculos), fechar caminhos (com
  tolerância), associar formas, otimizar formas, eliminar duplicados, inverter direção, converter em
  curvas/bitmap, traçar imagem, texto no caminho, teclas de atalho editáveis, configurações.
- **Ferramentas**: selecionar, mover a vista, linhas, retângulo (com raio), elipse, polígono, estrela,
  triângulo/pentágono/hexágono/octógono, texto, medir, aparar (tesoura), editar nós (D I M L C S B),
  deslocar, solda, união, subtração, interseção, cortador, código QR e EAN-13, forma com medidas exatas.
- **Organizar**: agrupar/autoagrupar/desagrupar/separar, espelhar (H, V, na linha), girar 90°, 6
  alinhamentos + centros, distribuir (e espaçado), mesma largura/altura, encostar, mover para a página,
  matriz em grade e circular, copiar ao longo do caminho, cisalhar, contorno elástico, âncoras, bloquear,
  ordem de corte, **guias inteligentes ao arrastar** (centro/bordas com linha), menu do botão direito.
  **Disposição automática na mesa** (nesting por retângulos, girar 90°, vão e margem, contorna o resto),
  **reunir em H/V**, **redimensionar slots** (encaixes e furos retangulares), **dimensionar/rotacionar por
  dois pontos** (Ctrl+2).
- **Barras**: X/Y/largura/altura/%/girar/raio, seletor de 9 pontos, barra de texto (fonte, altura,
  negrito, itálico, maiúsculas, distorcer, soldado, alinhamento, entrelinha), interruptores Mover/Tamanho/
  Girar, paleta de 30 camadas.
- **Camadas**: linha/preenchimento/imagem, velocidade, potência mín./máx., passadas, intervalo, kerf,
  ângulo e incremento, bidirecional, hachura cruzada, sobrevarredura, guias (pontes), sobrecorte, preencher
  juntas, **entrada/saída do corte** (lead-in/out, do lado da sobra), **subcamadas**, ações em todas as camadas, biblioteca
  de materiais.
- **Imagem**: limiar, pontilhados (Floyd–Steinberg, Jarvis, Stucki, Atkinson), tons de cinza, **meio-tom**
  (células/pol., ângulo), negativo, brilho/contraste/gama.
- **Otimização**: furos antes do contorno, vizinho mais próximo, remover linhas sobrepostas.
- **Laser (sem mover a máquina)**: prévia do percurso com tempo, gerar G-code GRBL, simulador, matriz de
  testes de material/intervalo/passadas, rotativo (rolo/mandril), **configurações da máquina** (mesa,
  origem, M3/M4, S máx.), conexão somente leitura e relatório da máquina.
- **Produção**: frisos, gabaritos, produção em lote, texto variável com planilha.

## O que ainda falta criar no RedBlack
### Dá para fazer agora (não depende da máquina)
| Função do LightBurn | Situação | Esforço |
|---|---|---|
| Importar HPGL / Gerber | ⬜ | médio cada |
| Estrela dupla, círculo tangente a 3 círculos | ⬜ | pequeno cada |
| Nós: estender linha, alinhar nós | ⬜ | pequeno |
| Distorção de 4 / 16 pontos | ⬜ | médio |
| Assistente de booleanas | ⬜ | pequeno (as operações já existem) |
| Máscara e recorte de imagem | ⬜ | médio |
| Unidades em polegadas, tema claro, DPI do SVG | ⬜ | pequeno/médio |
| Biblioteca de artes, pacotes, nova janela | ⬜ | médio |

### Depende da máquina (Etapas 14–16 do ROADMAP)
Mover o laser e ir à origem, enquadrar, posição do usuário e "começar de", **iniciar/pausar/parar o trabalho
e enviar para a máquina**, fila, comando de air assist, teste de foco, calibração do rotativo na máquina,
console de comandos.

### Fora do escopo (a S30 não tem)
Câmera, galvo, LiDAR, Wi-Fi/Ruida/controladores DSP, impressão e corte com câmera.

## Observação importante
Hoje o RedBlack **gera** o arquivo G-code, mas **não envia** à máquina (por segurança, até a SCULPFUN chegar e
os valores dela serem conferidos). Para gravar, o arquivo precisa ser enviado por outro programa ou pelo
cartão SD da máquina.
