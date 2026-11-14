# REA — Reverse Engineer Anything

## Identidade (confirmado)
- Pacote npm `rea-agents` 6.4.0, CLI `rea` (`%APPDATA%\npm\rea.ps1`), licença MIT.
- Repositório declarado no pacote: https://github.com/morluto/rea
- Também acessível como servidor MCP `rea` nesta sessão do Claude Code.

## Ambiente (`rea doctor`, 2026-11-07)
- node 22.23.2, host win32 x64 — ok.
- Ghidra 12.1.4 em `C:\Tools\ghidra\ghidra_12.1.4_PUBLIC` — ok.
- Hopper ausente (`missing_analysis_engine`); `healthy: false` no geral por causa disso.

## Uso na Etapa 1
Objetivo: obter a organização da janela principal do LightBurn como referência.

| Comando | Resultado |
|---|---|
| `rea --version` | `6.4.0` |
| `rea capture-native-ui-scenario <LightBurn.exe> --pid <pid>` | Erro: exige `--window-id` |
| idem com `--window-id` e `--steps '[...]'` via PowerShell 5.1 | Erro `invalid_format`: o PowerShell remove as aspas do JSON ao chamar o executável |
| MCP `capture_native_ui_scenario(pid, window_id, steps=[wait 300])` | Erro `target_unavailable`: requer `open_binary` antes (sessão de análise) |

**Bloqueio documentado:** a captura de UI do REA depende de abrir o binário numa sessão de análise
(Ghidra, executável de 33 MB). Isso não foi feito nesta etapa, pois a interface só precisava da
organização visual. Alternativa usada: captura de tela da janela (API Win32 `CopyFromScreen`).

**Nenhuma análise binária (estática ou dinâmica) do LightBurn foi realizada até agora.**

## Uso na Etapa 2
Não utilizado. Zoom/deslocamento são comportamentos de interface observáveis e documentados
publicamente (docs/REFERENCIA.md); análise binária não traria informação adicional útil à etapa.

## Uso na Etapa 3
Não utilizado. O comportamento necessário (seletor de 9 pontos, trava, sentido de rotação, Shift)
está documentado publicamente. A única dúvida relevante — se o campo Girar é absoluto ou incremental —
seria melhor respondida observando a interface com a avaliação iniciada do que por análise binária.

## Uso na Etapa 4
Não utilizado. O formato de projeto é próprio; ler `.lbrn2` é melhoria futura, e o formato do
LightBurn é XML legível, sem necessidade de análise binária para isso.

## Uso na Etapa 5
Não utilizado. SVG é um padrão público (especificação W3C usada como referência, inclusive o
algoritmo de arcos F.6); o comportamento de importação da referência não foi observado.

## Uso na Etapa 6
Não utilizado. PNG (pHYs), JFIF e EXIF são formatos públicos; o comportamento de DPI padrão da
referência foi levantado no fórum oficial (docs/REFERENCIA.md).

## Uso na Etapa 7
Não utilizado. Comportamento de texto/fonte ausente levantado na documentação oficial; renderização
de fontes é feita pelo Qt.

## Uso na Etapa 8
Não utilizado. Atalhos e modificadores levantados na documentação oficial; geometria é própria.

## Uso na Etapa 9
Não utilizado. Organização de camadas levantada na documentação oficial. Em etapas de G-code e
comunicação (11–16), a análise do LightBurn com REA pode ser útil para conferir sequências de comandos;
será avaliada lá, sempre sobre cópia do executável.

## Uso na Etapa 10
Não utilizado. Comportamento da prévia levantado na documentação oficial; algoritmos (varredura,
tempo) são próprios. O REA fica reservado para conferir sequências de G-code e protocolo (Etapas 11–16),
se necessário, sobre cópia do executável.

## Uso na Etapa 11
Não utilizado. O dialeto GRBL é público; a análise binária do gerador da referência não substituiria
a confirmação na própria máquina, que é o que falta. Avaliar o REA de novo se for preciso reproduzir
alguma sequência específica de comandos da referência.

## Uso na Etapa 12
Não utilizado. O simulador segue a documentação pública do firmware GRBL; o comportamento que importa é
o do controlador, não o da referência. Na Etapa 13 a fonte de verdade será a própria máquina.

## Uso na Etapa 13
Não utilizado. A fonte de verdade é a própria máquina (`$I`, `$$`), lida em modo somente leitura.

## Próximo uso previsto
Etapa 2+: `open_binary` numa **cópia** de `LightBurn.exe` fora de `Program Files`, restrito aos módulos
da etapa em curso. Licença/ativação/avaliação ficam fora do escopo.
