# Máquina

Equipamento informado: SCULPFUN S30 Pro Max (variante 20 W ópticos anunciados), USB, air assist,
rotativo a confirmar.

| Item | Valor | Estado |
|---|---|---|
| Controlador / firmware | GRBL (fabricante orienta "GRBL-M3" no LightBurn) | **público, não verificado na máquina** |
| Protocolo | serial GRBL 1.1 (texto, `ok`/`error`) | **inferido, não verificado** |
| Porta / driver | — | **não verificado** |
| Potência máxima ($30) | 1000 (padrão GRBL; guia geral do LightBurn) | **não verificado** |
| Modo laser ($32) | deve ser 1 (G0 apaga o feixe) — pré-requisito do G-code gerado | **não verificado** |
| Homing ($22) | relatos de fórum citam homing habilitado | **não verificado** |
| Área útil | difere entre módulos 10 W e 20 W (fórum); UI usa 400 × 400 mm só como demonstração | **não verificado** |
| Velocidade máxima ($110/$111) | — (perfil usa 20 000 mm/min como suposição) | **não verificado** |
| Origem | UI e G-code usam inferior esquerda como demonstração | **não verificado** |
| Comando de air assist | — (não emitido no G-code) | **não verificado** |
| Rotativo | — | **não verificado** |

Fontes públicas consultadas (2026-11-07):
[Sculpfun — setting up the software](https://sculpfun.com/blogs/blog/setting-up-the-software),
[LightBurn — Common GRBL setups](https://docs.lightburnsoftware.com/CommonGrblSetups.html),
[Fórum LightBurn — Sculpfun manual setup](https://forum.lightburnsoftware.com/t/sculpfun-manual-setup/109726),
[Fórum LightBurn — Homing cycle](https://forum.lightburnsoftware.com/t/homing-cycle-is/109330),
[Sculpfun — S30 Series firmware](https://github.com/Sculpfun-design/S30-Series-Software-Firmware).

## Kit informado pelo usuário (2026-11-08)
SCULPFUN S30 Pro Max 20 W com air assist automático e conjunto de rolos rotativos (máquina ainda não
recebida). Dados públicos, **todos não verificados**:

| Item | Público | Fonte |
|---|---|---|
| Potência óptica | 20 W (luz, não elétrica); consumo ~120 W | página do fabricante |
| Área | 370 × 360 mm padrão, ampliável 900 × 370 / 900 × 890 (outros anúncios: 410 × 400) | fabricante / revendedor |
| Placa | 32 bits com air assist; cartão SD | fabricante |
| Rotativo | rolo vendido em kit; uso no programa: Etapa 19 | fabricante |

A área da mesa no programa continua 400 × 400 mm demonstrativa até a leitura de `$130/$131` na máquina.

### Biblioteca de materiais (painel Materiais)
Valores de `redblack/materiais.py` = tabela de teste publicada pelo revendedor GeekBuying para a S30 Pro
Max 20 W ([página](https://www.geekbuying.com/item/SCULPFUN-S30-Pro-Max-20W-Laser-Engraver-Cutter-517193.html),
consultada em 2026-11-08), que diz textualmente que são "para referência" e devem ser ajustados à espessura
real. São **pontos de partida não validados**, marcados assim na interface. O intervalo de 0,1 mm das
gravações não consta na tabela (suposição). Inconsistência na própria tabela: paulownia 10 mm = 2 passadas,
15 mm = 1 passada. Depois de testar, use "Salvar camada como material…" para guardar o valor real ([Meu]).

Nenhum dado de anúncio ou fórum foi tomado como definitivo. A leitura do próprio controlador já está
implementada (painel Máquina → Conectar → Salvar relatório da máquina, somente leitura), mas em
2026-11-08 a máquina não estava conectada (só COM1 presente). Os valores acima continuam não verificados.
