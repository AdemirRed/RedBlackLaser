# Roteiro

Fonte: seção 7 do plano. Uma etapa por vez; cada uma só começa após avaliação da anterior.

| Etapa | Funcionalidade | Depende de | Estado |
|---|---|---|---|
| 1 | Interface (menus, barras, área base, painéis, status, tema, layout persistente) | — | Aprovada |
| 2 | Área gráfica: zoom, deslocamento, grade, réguas e mm | 1 | Aprovada |
| 3 | Objetos: seleção, mover, redimensionar, girar, alinhar | 2 | Aprovada |
| 4 | Desfazer/refazer, salvar/abrir projeto próprio | 3 | Aprovada |
| 5 | Importar SVG (subconjunto) | 3 | Aprovada |
| 6 | Importar PNG/JPG | 3 | Aprovada |
| 7 | Texto e fontes | 3 | Aprovada |
| 8 | Formas e edição vetorial básica (inclui agrupar/desagrupar) | 3 | Aprovada |
| 9 | Camadas e parâmetros | 3 | Aprovada |
| 10 | Prévia de percurso e estimativa | 9 | Aprovada |
| 11 | G-code vetorial simples | 9, máquina confirmada | Aprovada (perfil ainda NÃO confirmado na máquina) |
| 12 | Simulador de controlador | 11 | Aprovada |
| 13 | Comunicação serial e leitura de estado | 12 | Entregue no simulador; validação na máquina pendente |
| 14 | Movimentação, origem, enquadramento | 13 | Pendente |
| 15 | Execução, pausa, cancelamento | 14 | Pendente |
| 16 | Air assist | 15 | Pendente |
| 17 | Gravação raster | 6, 15 | Pendente |
| 18 | Materiais e matriz de testes | 9 | Pendente |
| 19 | Rotativo | 15 | Pendente |
| 20 | Gabaritos e lote | 4, 18 | Pendente |
| 21 | Custos, histórico, backup | 4 | Pendente |
| 22 | Empacotamento e distribuição | todas as anteriores necessárias | Pendente |

## Ideia para a próxima etapa (pedido do usuário, 2026-11-09): projetor no lugar da câmera
Em vez da câmera do original, usar um **projetor** apontado para a mesa da máquina para desenhar a imagem do
trabalho exatamente em cima da peça (ver antes de gravar onde e como vai ficar). Precisará de: janela em tela
cheia no projetor (segundo monitor), calibração por pontos (o laser/usuário marca cantos conhecidos da mesa e o
programa calcula a correção de perspectiva/escala), modo "só contornos" bem visível e ajuste fino de posição.
