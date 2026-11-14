# Validação

## Texto variável e arquivos recentes — 2026-11-08

`tests/test_variaveis_recentes.py` (12): marcadores com data fixa (08/11/2026 14:05), `{n:3}`=007,
`{nome}`/`{MODELO}` sem diferenciar maiúsculas, `{{}}`, desconhecido `{?Apelido}`; CSV do Excel em
Windows-1252 com acentos, vírgula, tabulação com BOM, colunas faltando, vazio/sem dados/linhas demais
recusados; avançar para na última linha; dados do projeto inválidos recusados. Janela: contorno do texto =
contorno do valor ("João da Silva 001" → "José 001" → "José 002", desfazer); texto fixo com chaves não muda;
aviso de marcador sem valor; texto variável dentro de grupo; projeto reabre sem o CSV original na mesma
linha; lote de 3 arquivos com nomes acentuados, conteúdos diferentes, dentro da área, documento intacto,
segunda execução recusada (não sobrescreve); lote sem planilha 10/12/14; recentes: máx. 8, topo ao
reabrir, sem repetidos, removido se apagado, limpar, persistem entre janelas. Total 234/234.
Visual: `texto_variavel.png`, `texto_variavel_dialogo.png`.

## Duplicar e cantos arredondados — 2026-11-08

`tests/test_arredondar_duplicar.py` (8), valores à mão: retângulo 40×20 com raio 5 mantém a caixa e mede
2·60 − 8·5 + 2π·5 (erro < 0,1 %); ponto médio de cada arco a 5 mm do centro do canto (erro < 0,03 %);
raio 100 em 40×20 → estádio 2·20 + π·20; triângulo 3 cantos; linha aberta só o canto do meio;
ponto colinear e elipse inalterados; raio 0 não faz nada. Janela: Ctrl+D duplica 2 objetos no mesmo lugar,
texto continua texto, área de transferência intacta, desfazer; retângulo desenhado com raio 4 tem 4 arcos;
Arredondar ignora elipse e texto e informa; raio em mm reais após escalar 2×. Total 222/222.
Visual: `cantos_duplicar.png`.

## Ajustes do usuário — 2026-11-08 (encaixe e fechamento de linhas)

Reprodução do defeito na plataforma real (QTest, eventos do Qt): linha com 3 pontos e clique no início
desviado (6, 6) px → não fechava (tolerância 8 px). Depois da correção: desvios de 0, 5,7, 8,5 e 11,3 px
fecham; 17 px permanece aberta (fora do raio, como esperado).

`tests/test_encaixe.py` (8): cantos/centro de retângulo e prioridade canto > centro; texto (caixa) e grupo
girado (nós transformados); linha fecha com clique fora do início e o indicador mostra "fechar"; Medir de
canto a canto com mão imprecisa = 144,22 mm exatos (ΔX +120, ΔY −80); Alt e o botão desligam o encaixe;
retângulo começa exatamente no canto de outro; nó arrastado encaixa no canto de outro objeto; Novo projeto
descarta linha em andamento. Total 214/214.

## Etapa 13 — 2026-11-08

Critério do roadmap: conexão e identificação sem executar trabalho ou emitir laser.

### Ambiente
Portas seriais presentes: só COM1 (placa-mãe). Nenhum adaptador USB-serial (CH340/FTDI/CP210x).
**A SCULPFUN não estava conectada: validação física NÃO realizada.**

### Automática — 206/206 OK (`tests/test_conexao.py` 14 + `tests/test_painel_maquina.py` 4)
| Teste | Verifica |
|---|---|
| ParserTest (3) | status com MPos/WPos/FS/F, número inválido ignorado, linhas lixo e enormes recusadas; boas-vindas GRBL e FluidNC; `$130=410.500`; avisos ($32=0, área ≠ 400, $20=0) |
| test_conecta_identifica_e_fica_lendo_status | simulador: Conectado, firmware 1.1h, `[VER]`, `[OPT:V,15,128]`, $30/$32/área, status Idle, `?` periódico |
| test_nada_alem_de_consultas_foi_enviado | bytes escritos = só `?`, `$I`, `$$`; trilha vazia; laser nunca armado |
| test_comandos_proibidos | G0, $X, $H, M3, $J, $32=0, Ctrl-X, `~`, `!` recusados; `$G` aceito |
| test_placa_que_nao_reinicia_ao_abrir | sem boas-vindas: após 2,5 s pergunta `?` e identifica |
| test_sem_resposta_vira_falha_e_fecha | porta muda: falha "Sem resposta" e porta fechada |
| test_maquina_em_alarme_nao_e_desbloqueada | homing ligado (Alarm): nunca envia $X/$H |
| test_cabo_removido_e_reinicio_da_placa | reset na placa → reidentifica; cabo puxado → falha "Nada será retomado"; não reconecta sozinho |
| TransporteSerialTest (2) | linhas partidas, CRLF, 70 KB de lixo descartado; erro de recurso fecha a porta |
| PainelMaquinaTest (4) | painel conectado ao simulador mostra estado, firmware, área, $32, aviso; registro sem status; relatório JSON; desconectar; procurar portas não abre nada; porta que não abre vira falha |

Teste antigo ajustado (intencional): "nada de máquina habilitado" agora libera só Conectar, Procurar
portas e Salvar relatório; movimento, laser e execução continuam desabilitados.

### Visual
`maquina_simulador.png`: painel conectado ao simulador, somente leitura, com aviso de $20 = 0.

### Corrigido durante a etapa
Rodapé "Máquina: desconectada" era texto fixo; agora acompanha a conexão.

### Pendente
Conexão real com a SCULPFUN e preenchimento de docs/MAQUINA.md com os valores lidos.

## Etapa 12 — 2026-11-07

Critério do roadmap: respostas, erros, desconexão e estados reproduzíveis.

### Automática — 188/188 OK (`tests/test_simulador.py`: 18 novos)
| Teste | Verifica |
|---|---|
| test_boot_status_e_informacoes | boas-vindas; `?` → `<Idle|MPos:0.000,0.000,0.000|FS:0,0|Bf:15,128>`; `$I` com `[OPT:V,15,128]`; `$$` com $30=1000, $32=1, $130=400 |
| test_erros_com_codigos_do_grbl | 22 (sem F), 20 (não suportado, inclusive G2), 2 (número), 1 (sem letra), 3 ($ inválido), 5 (homing desabilitado), 11 (linha longa); comentário/vazia = ok; erro não muda estado |
| test_trabalho_gerado_executa_igual_a_previa | G-code da Etapa 11 transmitido: todos ok, mm com laser = prévia, G0 sempre apagado, S=500, termina na origem, Idle, sem estouro, 0 s de laser parado, tempo = estimativa (±0,05 s) |
| test_planejador_cheio_segura_o_ok / estouro / transmissor | 17 linhas: 15 ok imediatos, os outros só após movimento; com planejador cheio, 150 bytes sem esperar → 22 perdidos e Bf:0,0; transmissor por contagem de caracteres: 300 linhas, 0 estouro |
| test_pausa_e_retomada | `!` → Hold, laser apagado, posição parada; `~` → conclui |
| test_reset_* | reset em movimento → ALARM:3 + boas-vindas, planejador vazio, laser apagado, G-code travado (error:9) até $X; reset parado → só boas-vindas |
| test_limite_por_software / transmissor_para_no_alarme | ALARM:2, laser e M3 desligados; transmissor para e aponta a linha 5 |
| test_homing_e_inicio_travado | $22=1 inicia em Alarm com mensagem; $H → Home, ok só ao terminar, posição 0 |
| test_jog_cancelamento_e_limite | Jog, cancelamento 0x85 a meio caminho (5 mm), G91 do jog não vaza, jog fora do limite = error:15 sem alarme, jog sem F = error:16 |
| test_modo_verificacao | $C: interpreta o trabalho inteiro sem mover nem emitir |
| test_m3_parado_e_detectado_m4_nao | M3 S300 parado 2 s → 2 s de risco medidos; M4 não soma; M5 apaga |
| ConexaoTest (2) | desconectar no meio: escrever/ler falham; reabrir = reinício limpo, nada retomado, M5; porta fechada falha |
| test_mesma_entrada_mesmo_resultado | duas execuções completas (preenchimento): respostas, trilha, status e tempo idênticos |

### Ferramenta de linha de comando
`python tools/simular.py exemplo.gcode` (arquivo da Etapa 11): 538/538 ok, 0 erro, 0 alarme, Idle na
origem, 1 958,9 mm com laser, 104,7 s simulados, 0 estouro, 0 s de laser parado.
Arquivo com X 450 e `--limites`: ALARM:2 apontando a linha 5, sem movimento, laser apagado.

### Problemas encontrados e corrigidos durante a etapa
1. Linha recusada (ex.: G1 sem F) alterava o modo modal: agora é descartada inteira, como no GRBL.
2. O simulador só processava linhas ao fim de cada pacote recebido (estouro irreal); agora a cada linha.
3. Respostas não lidas sobreviviam à desconexão; agora se perdem.
4. Ferramenta atribuía o alarme à linha errada.

### Não verificado
Comparação com um GRBL real (Etapa 13); aceleração; sequência real de mensagens em alarme.

## Etapa 11 — 2026-11-07

Critério do roadmap: saída determinística, unidades e limites verificados sem execução física.

### Automática — 170/170 OK (`tests/test_gcode.py`: 15 novos)
| Teste | Verifica |
|---|---|
| test_retangulo_texto_exato | G-code completo de um retângulo (doc (10,20)–(110,70) → máquina Y 380/330) idêntico a texto escrito à mão |
| test_deterministico | duas gerações com SHA-256 iguais; nunca "-0.000" |
| test_unidades_e_somente_comandos_permitidos | só G21 G90 M5 M3 G0 G1 M2; G21 e G90 antes do 1º movimento; sem G20/G91 |
| test_s_e_f_por_camada_modais_e_m4 | 12,5 % → S125; S/F só quando mudam; perfil M4; 12 G1 para 2 passadas + 1 camada |
| test_conferencia_relendo_o_gcode | verificador relê: comprimentos com e sem laser = percurso (tolerância do arredondamento a 0,001 mm), dentro da área, laser apagado no fim, S máx 200 |
| test_curva_tem_comprimento_correto | círculo Ø40: π·40 com erro < 0,1 % |
| LimitesTest (6) | 4 casos fora da área recusados; borda exata (0–400) aceita; área menor do perfil; F acima do máximo; nada para gerar; comando de laser inválido; verificador recusa G20, G91, G1 sem F, G2, movimento antes de G21/G90 |
| JanelaTest (3) | exportar grava exatamente o texto gerado, aviso de perfil não confirmado, sem .tmp residual; fora da área não cria arquivo; ações habilitadas sem módulo serial |

### Exportação real (plataforma Windows)
Exemplo com contorno (C01, 600 mm/min, 90 %) e nome "JOÃO" em preenchimento (C02, 3000 mm/min,
35 %, 0,5 mm): 546 linhas; duas exportações com SHA-256 idêntico (`6eaf5f41…`); releitura: 1958,9 mm
com laser, dentro da área, S máx 900, laser apagado no fim. Objeto até X 430 mm: recusado, nenhum arquivo.

### Não verificado
Execução em controlador GRBL real ou simulador de terceiros; valores reais de $30/$32/área da máquina.

## Etapa 10 — 2026-11-07

Critério do roadmap: movimentos e emissão diferenciados; tempo apresentado como estimativa.

### Automática — 155/155 OK (`tests/test_percurso.py` 15 + `tests/test_previa.py` 9; valores à mão)
| Teste | Verifica |
|---|---|
| Retângulo 100×50, 600 mm/min | trechos [vazio, corte, vazio]; corte 300 mm = 30 s; deslocamento ida e volta = 2·√(10²+380²) mm a 6000 mm/min; origem e retorno exatos |
| Passadas | 3 passadas = 120 mm de corte em 3 cortes; sem deslocamento extra (contorno fechado) |
| Camadas | ordem da lista (não do documento); Saída desligada exclui; Exibir desligado NÃO exclui; velocidades por camada (40 mm a 1200 → 2 s; a 300 → 8 s) |
| Círculo / grupo girado | perímetro π·40 com erro < 0,1 %; grupo 20×10 girado 90° cortado como 10×20 |
| Preenchimento | retângulo 40×10, intervalo 1: 10 linhas, 400 mm, 1ª esquerda→direita e 2ª direita→esquerda (coordenadas exatas), passo 1 mm entre linhas; círculo r=20: área/intervalo com erro < 0,5 % |
| Regra de preenchimento | anel 40×40 com furo 20×20: par-ímpar = 1200 mm; winding = 1600 mm (exatos) |
| Texto, imagem, forma minúscula | texto "I" preenche; imagem 10×5 mm a 0,5 = 100 mm; forma menor que o intervalo ganha 1 linha |
| Limite e desempenho | 3 × (400×400 a 0,01) recusado com mensagem citando a camada; 400×400 a 0,1 em < 3 s (medido 0,02 s) |
| Simulação | meio do corte (5 s a 600 mm/min) = 50 mm exatos, laser emitindo; início e deslocamento = vazio; além do fim = origem, 3 trechos |
| Mesa / tempo | percurso >400 mm e <0 mm detectado; formatos "0 s", "45 s", "1 min 00 s", "2 min 05 s", "1 h 02 min" |
| Janela (9) | fechada por padrão e objetos intactos; abrir mostra resumo/tabela/"≈ … (mínimo)" e esmaece (0,3) e fechar restaura (1,0); velocidade da camada muda a estimativa e desfazer a restaura; Saída desligada → mensagem e controles desabilitados; velocidade de deslocamento editável; controle deslizante → "CORTANDO", cabeça emitindo, fim na origem; Simular avança e para no fim; aviso fora da mesa e limite de linhas; projeto novo atualiza; nenhum módulo serial carregado |

Testes antigos ajustados (intencional): lista de painéis passa a incluir "Prévia do percurso", e o
teste "nada de máquina habilitado" exclui a ação de prévia (só calcula e desenha; não é comando de máquina).

### Visual (plataforma real)
`previa_corte_contorno.png`: 37 s de 3 min 27 s, cortando o contorno C01 com a cabeça cheia.
`previa_gravacao.png`: deslocamento sem laser com cabeça vazada; elipse sem Saída fora do percurso;
hexágono (2 passadas) planejado esmaecido. Totais do exemplo: contorno 520 mm (2·(180+80) ✓),
gravação do nome 4 036,5 mm, hexágono 480 mm (6·40·2 passadas ✓), tempo 3 min 27 s.

### Problemas encontrados e corrigidos
1. Fim da simulação parava 7e-15 mm antes do ponto final e contava um trecho a menos (arredondamento): fim exato.
2. Painel ocupava quase metade da janela: compactado e com altura inicial limitada.

### Não verificado
Comparação com tempo real de máquina; calibração da estimativa por aceleração; trabalhos com
muitos objetos pequenos (desempenho da sobreposição).

## Etapa 9 — 2026-11-07

Critério do roadmap: potência, velocidade, passadas, ordem e visibilidade independentes.

### Automática — 131/131 OK (`tests/test_camadas.py`: 16 novos)
| Teste | Verifica |
|---|---|
| test_padroes_e_cor / test_alterar_valida_e_nao_muta | padrões, cor da paleta, modo Imagem; 9 valores inválidos recusados (inclui mín > máx, passadas 2,5); original intacto |
| test_parametros_independentes | C01 potência 55 + velocidade 2500 e C02 passadas 4 + preenchimento: nenhuma afeta a outra; 4 passos de desfazer |
| test_valor_invalido_recusado_sem_alterar | mín 50 > máx 20: recusado, sem passo no histórico, mensagem |
| test_formulario_edita_camada_selecionada | campo Velocidade altera só a camada selecionada; tabela atualiza |
| test_ordem_e_desfazer | C02 sobe; subir no topo não muda nada; desfazer restaura |
| test_exibir_independente_de_saida / test_checkbox_da_tabela | ocultar C02 esconde só a elipse e a tira da seleção, saída inalterada; desligar saída não oculta; Selecionar tudo ignora ocultos; marcações da tabela |
| test_paleta_atribui_camada_e_cor / test_grupo_* | atribuição muda camada, cor e traço; grupo recebe camada em todos os filhos; grupo some só quando todas as camadas dos filhos estão ocultas |
| test_camada_com_imagem_fica_em_modo_imagem | camada com imagem fixa em Imagem; modo travado; intervalo habilitado |
| test_projeto_* / test_camadas_invalidas_no_arquivo | ordem, nome e parâmetros idênticos após salvar/abrir; projeto v4 ganha camadas padrão e "IMG" vira C01; id inválido, campo extra/ausente, repetida, mín > máx recusados |

### Visual
`camadas.png`: 4 camadas (Gravação nome em preenchimento no topo, Corte contorno 600 mm/min 90 % ×2,
C03 com saída desligada, C04 oculta — hexágono não aparece).

### Não verificado
Mouse físico; muitas camadas/objetos (desempenho).

## Etapa 8 — 2026-11-07

Critério do roadmap: retângulo, círculo e caminhos editáveis com medidas previsíveis.

### Automática — 115/115 OK (`tests/test_formas.py`: 18 novos)
| Teste | Verifica |
|---|---|
| test_caixa_do_arraste | arraste normal, invertido, Shift (quadrado), Ctrl (centro), ambos: caixas exatas |
| test_medidas_exatas | retângulo/elipse = caixa exata; pontos do círculo no raio (erro < 0,03 %) |
| test_poligono_regular | 3/5/6/8 lados: raio exato, vértice no topo, lados iguais; hexágono 10√3 × 20 |
| test_angulo_45 / test_nos_* | Shift 45°; retângulo e elipse com 4 nós; mover canto, início fechado, topo da elipse (tangente preservada); linha aberta |
| GrupoTest (3) | agrupar mantém caixa; girar 90° + escala 2 e desagrupar = geometria esperada (1e-9); texto continua TextShape; grupo aninhado salvo/aberto idêntico; 34 níveis e JSON com 100 000 colchetes recusados |
| JanelaTest (9) | retângulo = exatamente a caixa arrastada e volta a Selecionar; círculo Shift+Ctrl do centro; polígono com 5 lados da barra; clique sem arraste não cria; linhas fechada/Enter/Esc; Shift 45° e duplo clique sem ponto duplicado; nó arrastado com o mouse e desfeito; sem nós em texto; agrupar → largura 120 → desagrupar proporcional e desfazer |

### Visual (plataforma real)
`formas_nos.png`: nós do retângulo editado (canto +20/+15 mm → 140 × 75 mm), círculo 60, hexágono
51,96 × 60, linha 150 × 50. `formas_grupo.png`: grupo retângulo + texto "João" girado −10°.

### Problema encontrado e corrigido
JSON com aninhamento extremo derrubava a leitura (RecursionError); agora vira mensagem de erro.

### Não verificado
Mouse físico; muitos nós (desempenho); grupos muito grandes.

## Etapa 7 — 2026-11-07

Critério do roadmap: acentos, alinhamento e fonte ausente tratados; conversão em curvas avaliada.

### Automática — 97/97 OK (`tests/test_texto.py`: 14 novos)
| Teste | Verifica |
|---|---|
| test_altura_e_a_do_x_maiusculo_exata | X mede 3 / 10 / 37,5 mm, normal e negrito (erro < 1e-9) |
| test_acentos_e_cedilha | ÁÉÍÓÚ sobem acima da maiúscula com glifos próprios; ç desce abaixo da base; ÃÕÂÊÔÀÜ ºª desenham |
| test_alinhamento | linhas "A" e "AAAAAAAA": esquerdas iguais, centros iguais e na origem, direitas iguais (±0,5 mm) |
| test_entrelinha | 200 % dobra a distância entre linhas de base |
| test_fonte_ausente_detectada_e_ainda_desenha | detecção (sem diferenciar maiúsculas) e desenho com substituta |
| ProjetoTextoTest (2) | ida e volta de parâmetros e contorno; mesmo arquivo com fonte inexistente abre com contorno idêntico; parâmetros inválidos recusados |
| JanelaTest (7) | clique cria na posição e volta a Selecionar; cancelar não cria; duplo clique edita preservando matriz e desfaz; clique entre letras seleciona; Largura 100 mm aplicada; converter mantém contorno e caixa idênticos e desfaz; abrir com fonte ausente avisa e permite editar escolhendo outra |

### Visual (plataforma real do Windows)
`texto_area.png`: "Facas Artesanais / João & Conceição / ÁÉÍÓÚ ãõ ç" (Arial negrito, centralizado),
"Itálico à direita" (Times, à direita do ponto), X de 30 mm = 30,000000 mm, texto girado 20°.
`texto_dialogo.png`: diálogo com aviso de fonte inexistente.

### Problemas encontrados e corrigidos
1. Plataforma offscreen dos testes não tinha fontes (0 famílias): `QT_QPA_FONTDIR` aponta para as fontes do Windows.
2. Duplo clique em texto selecionado acertava a caixa de seleção.
3. Botões padrão do Qt apareciam em inglês ("Cancel"): tradução pt_BR do Qt carregada.

### Não verificado
Projeto aberto em outra máquina real sem a fonte; fontes de traço único; textos muito longos.

## Etapa 6 — 2026-11-07

Critério do roadmap: dimensões físicas e proporção corretas; imagem original preservada.

### Automática — 83/83 OK (`tests/test_importar_imagem.py`: 16 novos)
Imagens geradas no próprio teste (PNG escrito à mão para controlar o `pHYs`; JPEG do Qt com JFIF
alterado; EXIF mínimo inserido).

| Teste | Verifica |
|---|---|
| test_png_com_dpi_do_qt | 600×300 px a 300 dpi = 50,8 mm (valor exato do pHYs inteiro, erro < 1e-9) |
| test_png_sem_phys_e_com_unidade_desconhecida | sem pHYs ou unidade 0 → 96 dpi, sinalizado |
| test_png_dpi_diferente_por_eixo | X e Y com DPI diferentes |
| test_jpeg_jfif_dpi_dpcm_e_sem_densidade | dpi, pontos/cm (100 → 254 dpi), unidade 0 → padrão |
| test_orientacao_exif_troca_eixos_e_dpi | EXIF 6: 40×20 px vira 20×40; mm usam o DPI do eixo certo |
| test_original_preservado_byte_a_byte / test_extensao_errada_usa_conteudo / test_invalidos | bytes idênticos e SHA-256; PNG com nome .jpg; GIF, vazio, PNG truncado, JPEG lixo recusados |
| ProjetoComImagemTest (3) | ida e volta com bytes e matriz idênticos; SHA/base64/formato/ausente recusados; projeto versão 1 ainda abre |
| JanelaTest (5) | campos mostram mm corretos; largura 80 com trava mantém 2:1; desfazer remove; aviso de 96 dpi com texto exato; GIF não altera nada; pixel vermelho da imagem aparece no centro do objeto na tela; copiar/colar + salvar + reabrir mantêm os bytes originais e a orientação EXIF |

### Arquivos reais (máquina do usuário, somente leitura de dimensões/DPI)
12 PNGs em Downloads/Pictures: todos abertos; nenhum tinha DPI gravado → 96 dpi assumido e sinalizado.
Nenhum JPEG encontrado nessas pastas.

### Visual
`importacao_imagem.png`: PNG de 1936×1056 px (pHYs 96 dpi) = 512,30 × 279,44 mm; reduzido a 200 mm
de largura com proporção e girado −8°: caixa 213,24 × 135,86 mm (calculado: 200·cos8° + 109,09·sin8° = 213,24).

### Não verificado
JPEG com DPI só no EXIF (sem JFIF) de câmera real; perfis de cor/CMYK; imagens muito grandes (desempenho).

## Etapa 5 — 2026-11-07

Critério do roadmap: unidade, escala e transformações testadas; elementos sem suporte sinalizados.

### Automática — 67/67 OK (`tests/test_importar_svg.py`: 20 novos; valores esperados calculados à mão)
| Grupo | Casos |
|---|---|
| Unidades/escala | viewBox 200×100 em 100×50 mm → escala 0,5; 1in, 72pt, 10cm, 6pc, px puro e sem width = 25,4/10 mm exatos; unidade no próprio elemento (10mm, 1in); viewBox deslocado; meet centraliza (25,0,50,50); none estica; `%` gera aviso |
| Transformações | ordem SVG (translate·scale ≠ scale·translate), aninhamento, rotate(90), rotate(90 5 5), matrix, skewX/skewY 45° |
| Caminhos | H/V/Z, relativos, lineto implícito, números colados (`L10-5`), S e T com reflexo (extremos 7,5 e 5), arcos sweep 0/1, elipse girada 90°, raio pequeno ampliado, flags coladas, círculo completo; ponto no meio do arco no raio (erro < 0,03 %) |
| Elementos | círculo, elipse, linha, polilinha, polígono, rect com rx; text/image/use contados; ocultos (atributo e style) e vazios contados; title/defs/style silenciosos; fill-rule |
| Segurança/erros | `<!ENTITY>` recusado, XML truncado, raiz não-SVG, codificação ISO-8859-1 declarada |
| Janela | importação seleciona, mostra 30×15 nos campos, relatório "text: 1", desfazer remove; SVG inválido/sem formas não altera nada nem entra no histórico; amostra do repositório 100×60 mm |

### Arquivos reais (máquina do usuário, somente leitura)
12 SVGs encontrados em Downloads: 12 importados; único elemento sem suporte encontrado foi
`radialGradient` (sinalizado). `qrcode_pix.svg` contém apenas um retângulo e um texto (não é um QR
real): importado como 1 retângulo de 52,92 mm (200 px a 96/pol) + aviso de texto ignorado.

### Visual
`importacao_svg.png`: amostra (moldura 100×60, círculo Ø20, quadrado 10 girado 45° = caixa 14,142,
semicírculo 20×10) com medidas idênticas às esperadas no painel Objetos.

### Não verificado
SVGs de Illustrator, CorelDRAW e Inkscape; arquivos muito grandes (desempenho).

## Etapa 4 — 2026-11-07

Critério do roadmap: alterações reversíveis e projeto recuperado sem perda.

### Automática — 47/47 OK (`tests/test_projeto.py`: 12 novos)
| Teste | Verifica |
|---|---|
| test_ida_e_volta_sem_perda | objetos girados 33,3333°, escalados 1,23456789 e espelhados: caminho elemento a elemento, matriz, nome, camada e cor idênticos após salvar/abrir; sem .tmp residual |
| test_conteudo_versionado_em_mm | JSON com formato, versão 1, unidade mm; acentos preservados |
| test_arquivos_invalidos_sao_rejeitados | não-JSON, outro formato, versão futura, outra unidade, matriz curta, NaN, comando desconhecido, cor inválida |
| test_abrir_invalido_preserva_documento_atual | erro exibido e documento inalterado |
| test_salvar_fechar_reabrir | largura 123,45 reaberta em outra janela com erro < 1e-9 mm; título sem `*` |
| test_desfazer_refazer_campos | 2 edições desfeitas = original exato; refeitas = editado exato |
| test_desfazer_arraste_e_setas | histórico "Mover", "Mover com setas"; voltar ao início = original exato |
| test_so_selecionar_nao_entra_no_historico | clique só seleciona; histórico vazio |
| test_desfazer_excluir_e_colar | objetos, nomes, painel e seleção restaurados |
| test_titulo_indica_alteracao_e_ponto_salvo | `*` aparece ao editar e some ao desfazer até o ponto salvo |
| test_novo_pergunta_e_cancelar_preserva / test_fechar_com_alteracao_cancelado_nao_fecha | cancelar mantém o documento e a janela |

### Entre processos
Processo 1 gira a elipse 30°, altera a largura do retângulo para 77,77 mm e salva; processo 2 abre o
arquivo: conteúdo idêntico ao esperado (3 objetos).

### Problemas encontrados e corrigidos
1. Testes antigos travavam no diálogo "salvar alterações?" ao fechar: a pergunta virou método substituível.
2. Sinal tardio da cena ao destruir a janela acessava a caixa de seleção já apagada: verificação adicionada.

### Não verificado
Diálogos de arquivo do Windows (uso manual), caminhos de rede/OneDrive, disco cheio.

## Etapa 3 — 2026-11-07

Critério do roadmap: dimensões numéricas correspondem à geometria; proporção opcional funciona.

### Automática — 35/35 OK (`tests/test_objetos.py`: 18 novos)
| Teste | Verifica (tolerância) |
|---|---|
| test_medidas_da_elipse_sao_exatas | elipse 50×30 mede 50×30 sem traço/pontos de controle (1e-3 mm) |
| test_tamanho_numerico_com_cada_ancora | nos 9 pontos: tamanho 80×45 exato e ponto de referência fixo (1e-6) |
| test_posicao_numerica | X/Y por canto e por centro (1e-6) |
| test_girar | 60×30 girado 90° = 30×60; 45° = 63,64; ida e volta exata; positivo = horário |
| test_espelhar_mantem_caixa / test_alinhar / test_distribuir | caixa preservada; bordas/centros iguais; espaçamento igual |
| test_eixo_zero_nao_quebra | linha horizontal: largura muda, altura 0 permanece |
| test_campos_alteram_geometria_com_e_sem_proporcao | Largura 90 com trava → 90×45; sem trava Altura 20 → 90×20; X/Y pelo canto inferior esquerdo; Girar volta a 0 |
| test_clique_seleciona_e_campos_mostram_medidas | campos = 60×30, centro (70, 345); painel Objetos sincronizado |
| test_arrastar_objeto_move | arraste de 20 mm move 20 mm (±1,5 px) |
| test_alca_de_canto_mantem_proporcao_e_shift_libera | canto mantém 2:1 e canto oposto fixo; Shift altera a proporção |
| test_alca_de_lado_altera_um_eixo | lado direito: largura 90, altura 30 inalterada |
| test_alca_de_rotacao_com_shift_passos_de_15 | arraste até a direita = 90° exatos |
| test_setas_movem_1mm_e_shift_10mm | → 1 mm; Shift+↑ 10 mm para cima |
| test_shift_clique_adiciona_a_selecao | dois objetos selecionados, largura conjunta 140 mm |
| test_copiar_colar_excluir_selecionar_tudo | contagens, deslocamento +5 mm, painel atualizado |
| test_acoes_dependem_da_quantidade | alinhar/distribuir só habilitam com 2+/3+ objetos |

### Visual (`tools/capturar.py`)
- `selecao_retangulo.png`: alças e campos 70 / 345 / 60 × 30 mm.
- `selecao_multipla.png`: caixa conjunta 140 × 90,23 mm.
- `elipse_girada_30.png`: 45,84 × 36,06 mm. Valor analítico 45,83 × 36,06; diferença de 0,01 mm
  vem da aproximação da elipse por curvas Bézier no Qt (limitação registrada).

### Problemas encontrados e corrigidos durante a etapa
1. Shift+clique substituía a seleção: o Qt alterna a seleção ao soltar o botão; conversão aplicada também no soltar.
2. Painel Objetos acessava objetos já destruídos ao fechar/excluir: a sincronização passou a percorrer só a cena.

### Não verificado
Mouse físico/touchpad; muitos objetos (desempenho); objetos fora da mesa em grande quantidade.

## Etapa 2 — 2026-11-07

Critério do roadmap: coordenadas e escala consistentes em diferentes níveis de zoom.

### Automática — 17/17 OK (`python -m unittest discover -s tests`)
| Teste | Verifica |
|---|---|
| test_zoom_mantem_ponto_sob_cursor | após 5 sequências de roda (±), o ponto da cena sob o cursor varia ≤ 1,5 px |
| test_escala_limitada | zoom extremo para em 200 e 0,2 px/mm |
| test_reguas_consistentes_em_varios_zooms | em 5 escalas, px/mm medido nas réguas H e V = escala da vista (±1 %); régua alinhada à cena (±1 px) |
| test_deslocar_com_botao_do_meio | conteúdo acompanha o arraste do botão do meio (±1,5 px) |
| test_ajustar_a_mesa | Ctrl+0 / botão volta a mostrar a mesa inteira |
| test_coordenada_no_status | ponto (100, 50) de exibição aparece no status com erro ≤ 1 px |
| test_medir | arraste de (10,10)→(40,50) mede 50 mm; Esc desliga a ferramenta |
| test_geometria (5) | ida/volta de coordenadas, passos de grade, ticks sem erro de float, distância, rótulos |

### Visual (`tools/capturar.py`)
- `zoom_4x_retangulo.png` (6,95 px/mm): bordas do retângulo demo em X 40/100 e Y 330/360 coincidem com as réguas.
- `zoom_profundo_canto.png` (83,4 px/mm): grade de 0,1 mm, rótulos a cada 1 mm; canto (40, 360) coincide com as réguas.
- `medicao.png`: (40,40)→(100,70) da cena = 67,08 mm, ΔX +60, ΔY −30 (valor esperado √(60²+30²) = 67,08).

### Não verificado
Mouse físico (roda, botão do meio), touchpad, monitor com DPI ≠ 100 %.

## Etapa 1 — 2026-11-07

### Automática (`python -m unittest discover -s tests`) — 5/5 OK
| Teste | Verifica |
|---|---|
| test_paineis_existem | 4 painéis: Camadas, Máquina, Objetos, Materiais |
| test_nada_de_maquina_habilitado | todos os botões do painel Máquina e itens do menu Laser desabilitados; `QtSerialPort` não importado |
| test_layout_persistido | painel fechado continua fechado ao reabrir; "Restaurar layout padrão" reabre |
| test_area_de_desenho_ajustada | mesa inteira visível e centralizada no viewport |
| test_redimensionar | 1024×640, 1920×1080, 1280×800: janela aceita o tamanho, área central > 200 px, sem sobreposição com painéis |

### Visual (`tools/capturar.py`)
Capturas 1600×900 e 1024×640 inspecionadas. Falhas encontradas e corrigidas durante a etapa:
1. Área de desenho vazia — cena destruída pelo coletor do Python. Corrigido; coberto por teste.
2. Tabela de camadas mostrando 1 de 2 linhas — altura mínima ajustada.
3. Altura mínima da janela ~990 px — painéis colocados em rolagem; coberto por teste.

### Não verificado
Navegação apenas por teclado, leitor de tela, escala DPI ≠ 100%, Windows 11.
