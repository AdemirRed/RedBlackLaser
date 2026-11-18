# Como criar projetos de corte/gravação para o RedBlack Laser (guia para IA: Codex, Claude…)

Leia isto inteiro ANTES de gerar qualquer projeto. As regras vêm do dono, que testa tudo na máquina real
(SCULPFUN S30, GRBL 1.1h, mesa 365 × 370 mm). Projeto que não segue estas regras estraga MDF.

---

## 1. Regras do dono (obrigatórias)

| Assunto | Regra |
|---|---|
| Corte MDF 3 mm | **630 mm/min, 85 %, 2 passadas** (o `mt.corte_mdf(3)` ainda dá 650: sobrescreva `velocidade_mm_min=630`) |
| Corte MDF 6 mm | 600 mm/min, 85 %, 5 passadas |
| Potência | **NUNCA 100 %.** Máximo 85 % em qualquer camada |
| Gravação de desenho (rostos, mechas, pregas) | preenchimento, **2000 mm/min, 35 %**, 1 passada, intervalo 0,1 |
| Gravação fraca (códigos, marcas) | no mínimo 25 % a 3000 mm/min (a 10–15 % não aparece) |
| Rebaixo (assento de peça colada por cima) | preenchimento, **1500 mm/min, 60 %, 1 passada** (2 passadas é demais) |
| Folga do rebaixo | contorno da peça **+ 0,10 mm por lado** (sem folga ficou justo) |
| Encaixe macho/fêmea (rasgo, lingueta) | **sem folga**: rasgo = soma das espessuras |
| Margem | **2 mm** da borda da chapa e **2 mm** entre peças |
| Códigos das peças | gravar só se o dono pedir; em peça que vai ser pintada, camada com **Saída desligada** |
| Valores que o dono mudou num arquivo dele | **nunca sobrescrever** |

## 2. O que NÃO fazer (erros que já aconteceram)

1. **Não cortar por dentro sem necessidade.** Figura (bicho, pessoa, flor) corta **só pela borda de fora**. Na
   ovelha do presépio o contorno do PDF entrava pelos vãos da lã: o laser cortou a lã e sobraram só as linhas.
   Use a silhueta de fora (`presepio.silhueta`) e tire os furos que não são do desenho.
2. **Não deixar o tremido do PDF.** PDFs gerados por IA vêm "traçados de imagem": contornos em degraus de
   0,1–0,2 mm. **Sempre alise** (`luana.suavizar`, σ 0,3–0,7 mm; 1,2 em formas simples). Coração e oval que
   continuam com calombos: troque por forma perfeita na mesma caixa (`maria_olivia._coracao` / `_oval`).
3. **Não colocar em uma aplicação o que fica escondido embaixo de outra.** No PDF da Maria Olivia o cabelo
   continuava por baixo do vestido e dos ombros: a peça do cabelo tem que ser **só o que aparece**
   (cabelo − vestido − coroa − pele).
4. **Rebaixo sem detalhe pequeno.** Rebaixo é para a peça entrar: feche miolos de letra e vãos estreitos
   (< ~2 mm) e **nunca** rebaixe o que fica à mostra na base (rosto, braços, pescoço). Ver `_rebaixo_limpo`.
5. **Não gravar o que não precisa:** nada de gravação dentro do rebaixo, pontinhos soltos (< 0,8 mm²), nem a
   linha de contorno colada na borda da peça (parece queimado). Na base, só o que fica visível (o rosto).
6. **Não cortar lascas:** furo com menos de 1 mm de largura ou 15 mm² de área é sobra do traçado, não furo.
7. **Peça dentro do vão de outra corta ANTES do vão** (camadas C05/C06 antes de C02). Senão o miolo solto arrasta
   a peça. O `presepio.folhas` já faz isso.
8. **Não mudar a escala das peças** para "caber": reencaixe (nesting) as peças, nunca redimensione.
9. **Não enviar nada para a máquina.** O dono confere e corta.

## 3. Ordem das camadas (sai nesta ordem)

1. `C10` rebaixo (gravado, não atravessa) · 2. `C03` gravação do desenho · 3. `C04` traço · 4. `C07` números
5. `C05` furos de peças que estão dentro de vãos · 6. `C06` contorno dessas peças
7. `C02` furos/janelas/rasgos · 8. `C01` contornos externos (por último)

## 4. Como fazer (passo a passo)

O jeito certo é um **gerador Python** em `tools/projetos/<nome>.py` (repetível e testável), seguindo um dos
existentes. Escolha o mais parecido:

| Projeto | Use como modelo quando… |
|---|---|
| `maria_olivia.py` | porta-retrato com aplicações coladas, rebaixos com folga, cabelo/vestido, gravação de detalhes |
| `luana.py` | aplicações + rebaixo; tem `suavizar`, `_partes`, `_ret` (retângulo com cantos arredondados) |
| `presepio.py` | casa de encaixe 3D, muitas peças; tem `ler` de PDF por cor, `encaixar` (nesting), `folhas`, `mapa_pdf`, `previa`, `silhueta`, `zonas_de_cor` |
| `princesas.py` | PDF só com contornos (preto): separa contorno de fora × furos |
| `presepio_manual.py`, `presepio_pintura.py` | manual de montagem e guia de pintura em PDF |

Passos:

1. **Abra o PDF e entenda antes de codar.** `pymupdf`: `page.get_drawings()` (tipo `s`=traço, `f`=cheio,
   `fs`=cheio+traço; `color`/`fill`), `page.get_text()`. Ache as pranchas 1:1 (página do tamanho da chapa, ex.
   370 × 365 mm) e a tabela de medidas. Renderize em PNG (`get_pixmap`) e **olhe**.
2. **Leia as peças** em mm (`apollo_emily.caminho(d)`; `PT = 25,4/72`). Classifique pelo tamanho da tabela
   do PDF, não pela ordem. Confira cada medida (assert com tolerância de décimos).
3. **Limpe:** alise, tire lascas, recorte o que fica escondido, troque formas simples por perfeitas.
4. **Rebaixos:** com o MESMO contorno alisado da peça, + 0,10 mm por lado, só onde há MDF
   (`base − janela`), sem detalhe pequeno, sem cobrir rosto/braços.
5. **Encaixe nas chapas:** `presepio.encaixar(pecas, n_chapas)` (mesa 365 × 370, 2 mm) → `presepio.folhas`.
   Peças pequenas entram nas janelas das fotos (sobra que vira peça).
6. **Salve o .rbl** com `redblack.projeto.save`, cada peça num grupo com o nome `"<código> <nome>"`.
7. **Confira com imagem** (`presepio.previa` → PNG) e olhe peça por peça ampliada. Não entregue sem olhar.
8. **Valide o G-code** pelo MCP `gerar_gcode` de cada aba: área dentro da mesa e tempo razoável.
9. **Teste** em `tests/test_projeto_<nome>.py` (pula se o PDF não estiver no PC): medidas, sem lascas,
   rebaixo cobre a peça, nº de chapas. Rode também os testes dos outros projetos juntos.
10. **Entregue:** salve em `F:\Downloads\<Nome>_MDF_3mm_RedBlack.rbl`, copie para o outro PC
    (`scp ... administrator@192.168.0.110:C:/Users/Administrator/Desktop/LASER/`), commit no git.

Atenção: se o seu gerador mexer em `presepio.NOMES` (o mapa e a prévia usam), devolva como estava no fim
(ver o `gerar` de `luana.py`) — senão quebra os testes do presépio.

## 5. Rodar

```powershell
$env:QT_QPA_PLATFORM="offscreen"; $env:QT_QPA_FONTDIR="C:\Windows\Fonts"
python tools/projetos/maria_olivia.py "F:\Downloads\Maria_Olivia_Projeto_MDF3_Rebaixos.pdf" "F:\Downloads\Maria_Olivia_MDF_3mm_RedBlack.rbl" previa.png
python -m pytest -q tests/test_projeto_maria_olivia.py
```

## 6. Pelo MCP (projetos simples, sem PDF)

Para coisas pequenas (chaveiro, placa, teste) dá para usar as ferramentas do servidor MCP direto
(`docs/MCP.md`): `criar_projeto`, `configurar_camada`, `adicionar_forma`, `importar_arquivo`, `gerar_gcode`,
`abrir_no_redblack`. Mesmas regras de potência, velocidade e margem acima. Coordenadas em mm, origem no canto
superior esquerdo da mesa, Y para baixo; furos numa camada que sai antes do contorno (C02 antes de C01).
