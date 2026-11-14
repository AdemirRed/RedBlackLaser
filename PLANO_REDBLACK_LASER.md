# RedBlack Laser — Plano de análise e desenvolvimento incremental

## Frase para iniciar no Claude

> Leia integralmente o arquivo PLANO_REDBLACK_LASER.md, inspecione o ambiente e o projeto existente, verifique o acesso ao REA e ao LightBurn e comece pela preparação indispensável e pela Etapa 1: interface. Use o REA para compreender o funcionamento real da referência, documente as evidências e implemente nosso sistema com código próprio. Execute uma etapa por vez, valide o resultado e aguarde minha avaliação antes de avançar para outra funcionalidade.

## 1. Objetivo

Construir um aplicativo desktop próprio para preparar e executar trabalhos de gravação e corte a laser. Usar o LightBurn como referência funcional e de organização, estudando seu comportamento com o REA quando tecnicamente disponível. Desenvolver uma alternativa com identidade própria, interface em português e melhorias para os meus serviços.

Nome provisório: **RedBlack Laser**. Uso gratuito, sem expiração, limite de trabalhos ou ativação obrigatória. Não implementar licenciamento nesta versão. Uma futura distribuição deve continuar independente da instalação do LightBurn.

O projeto completo é uma direção de evolução, não uma promessa de equivalência imediata com todas as funções e controladores do LightBurn. A primeira entrega será somente a interface.

## 2. Equipamento inicial e informações a confirmar

- SCULPFUN S30 Pro Max, variante com potência óptica anunciada de 20 W.
- Conexão USB e assistência de ar.
- Acessório de rolos rotativos, cuja inclusão e modelo precisam ser confirmados.
- Computador Windows como alvo inicial; confirmar versão e arquitetura.
- Confirmar controlador, firmware, protocolo, drivers, dimensões úteis, origem e parâmetros diretamente na máquina/documentação correspondente.

Não converter dados de anúncios em parâmetros definitivos. Há divergências nas descrições sobre dimensões, fontes e acessórios. Não presumir que a gravação no metal da faca terá o mesmo resultado obtido em madeira: a validação de material é independente do desenvolvimento do programa.

## 3. Forma de trabalhar

1. Inspecionar o repositório antes de escolher tecnologias ou criar arquivos.
2. Preservar código e alterações existentes.
3. Manter o plano geral, mas implementar somente a etapa atual.
4. Dividir tarefas grandes em incrementos pequenos e executáveis.
5. Não misturar a interface inicial com conexão física ou processamento avançado.
6. Resolver decisões rotineiras de implementação autonomamente; perguntar somente quando faltar informação que altere o resultado.
7. Ao concluir uma etapa, mostrar o resultado e aguardar minha avaliação para iniciar a próxima.
8. Corrigir falhas da etapa atual antes de expandir o escopo.
9. Manter o aplicativo executável e a documentação atualizada a cada entrega.
10. Não marcar simulações, protótipos ou recursos incompletos como concluídos.

## 4. Uso do REA e análise do LightBurn

### 4.1 Verificação inicial

O usuário identifica REA como **Reverse Engineer Anything**, uma ferramenta CLI/MCP de código aberto. Antes de usá-la:

- Localizar o repositório oficial, verificar identidade, licença, documentação e versão. Não presumir comandos ou capacidades apenas pelo nome.
- Verificar se já existe instalação CLI ou servidor MCP acessível.
- Identificar sistema operacional, arquitetura, dependências e ferramentas auxiliares necessárias.
- Confirmar a localização e versão da instalação do LightBurn e seu acesso autorizado.
- Registrar comandos reais utilizados e saídas relevantes, sem dados pessoais ou chaves.
- Se a identidade do projeto REA for ambígua, pedir o link correto. Continuar o trabalho independente dessa dúvida.

### 4.2 Escopo da investigação

Empregar as capacidades reais do REA para análise estática e, quando suportada, análise dinâmica de:

- Estrutura do aplicativo, módulos e dependências.
- Relação entre ações na interface e processamento.
- Objetos, coordenadas, unidades, transformações e camadas.
- Formatos de projeto e configuração.
- Processamento de imagens e vetores.
- Geração de trajetórias e G-code.
- Protocolo de comunicação e tratamento de respostas.
- Air assist, movimentação, enquadramento e estados de execução.

Analisar somente os módulos necessários à etapa atual. Não fazer uma investigação indiscriminada de todo o programa antes de começar a interface.

Trabalhar sobre cópias separadas dos arquivos analisados e preservar a instalação original. Manter intactos a licença, a ativação e o período de avaliação do LightBurn. Esses mecanismos ficam fora do escopo. Não alterar relógio, identificadores ou arquivos para prolongar acesso.

Usar a investigação para escrever especificações e código independente. Não incorporar código descompilado, ícones, marcas, recursos gráficos ou bibliotecas proprietárias extraídas. A licença da ferramenta REA não licencia os componentes do programa analisado. Registrar licenças das dependências incorporadas ao nosso aplicativo.

### 4.3 Ciclo obrigatório por funcionalidade

1. Definir a função e um caso de teste pequeno.
2. Observar entradas, opções, saídas e mensagens de erro.
3. Investigar o fluxo relevante com o REA, se disponível.
4. Registrar evidências e separar **confirmado**, **inferido** e **não verificado**.
5. Produzir uma especificação independente de comportamento.
6. Implementar a menor versão útil com código próprio.
7. Comparar resultados em exemplos reproduzíveis.
8. Documentar diferenças e limitações.

Se o REA não funcionar, documentar o bloqueio e usar observação da interface, documentação pública e arquivos de teste próprios como alternativas. Não afirmar que realizou análise binária ou testes que não foram feitos.

## 5. Preparação mínima — antes da interface

- Inventariar projeto, ferramentas e dependências existentes.
- Registrar acesso ao REA, ao LightBurn e às referências visuais.
- Se necessário, pedir uma captura da janela principal, sem bloquear a estrutura independente dela.
- Escolher uma arquitetura desktop que suporte edição gráfica, arquivos locais, processamento e comunicação serial.
- Reutilizar a stack do projeto, quando adequada. Se começar do zero, comparar brevemente opções e justificar a escolha sem um planejamento prolongado.
- Criar estrutura mínima e comando de execução.

**Saída:** ambiente identificado, decisões iniciais documentadas e projeto que abre uma janela. Esta preparação não deve virar uma etapa extensa nem antecipar funcionalidades.

## 6. Etapa 1 — Interface primeiro

### Escopo

Reproduzir a organização funcional da janela principal da referência com componentes e identidade próprios:

- Barra de menus e ferramentas.
- Área central de desenho com representação visual de grade, réguas e origem.
- Painéis de objetos, camadas e parâmetros.
- Painel de controle da máquina e movimentação.
- Área de materiais, coordenadas e barra de status.
- Tema escuro legível, estados de foco visíveis e textos em português.
- Painéis redimensionáveis e persistência das preferências de layout.

Usar dados demonstrativos identificados. Funções ainda não implementadas devem ficar desabilitadas ou informar seu estado. Não enviar comandos nem conectar ao equipamento. Nesta etapa, a área gráfica é uma base visual; zoom, geometria e processamento virão depois.

### Critérios de aceite

- Aplicativo abre pelo comando documentado.
- Layout se adapta ao redimensionamento da janela sem sobreposição importante.
- Menus e painéis abrem e fecham conforme implementado.
- Textos, ícones e contraste permitem identificar as ferramentas.
- Recursos demonstrativos são distinguíveis de recursos reais.
- Nenhuma conexão ou emissão é iniciada.
- Capturas do aplicativo são apresentadas para minha avaliação.

## 7. Roteiro funcional após a interface

Cada linha é uma entrega separada e pode ser subdividida. Não executar todas de uma vez.

| Etapa | Funcionalidade | Validação mínima |
|---|---|---|
| 2 | Área gráfica: zoom, deslocamento, grade, réguas e mm | Coordenadas e escala consistentes em diferentes níveis de zoom |
| 3 | Objetos, seleção, mover, redimensionar, girar e alinhar | Dimensões numéricas correspondem à geometria; proporção opcional funciona |
| 4 | Desfazer/refazer e salvar/abrir projeto próprio | Alterações reversíveis e projeto recuperado sem perda |
| 5 | Importar SVG, começando por um subconjunto explícito | Unidade, escala e transformações testadas; elementos sem suporte sinalizados |
| 6 | Importar PNG/JPG | Dimensões físicas e proporção corretas; imagem original preservada |
| 7 | Texto e fontes | Acentos, alinhamento e fonte ausente tratados; conversão em curvas avaliada |
| 8 | Formas e edição vetorial básica | Retângulo, círculo e caminhos editáveis com medidas previsíveis |
| 9 | Camadas e parâmetros | Potência, velocidade, passadas, ordem e visibilidade independentes |
| 10 | Prévia de percurso e estimativa | Movimentos e emissão diferenciados; tempo apresentado como estimativa |
| 11 | G-code para um caso vetorial simples | Saída determinística, unidades e limites verificados sem execução física |
| 12 | Simulador de controlador | Respostas, erros, desconexão e estados reproduzíveis |
| 13 | Comunicação serial e leitura de estado | Conexão e identificação sem executar trabalho ou emitir laser |
| 14 | Movimentação, origem e enquadramento | Movimentos físicos graduais, dentro dos limites e com emissão desativada |
| 15 | Execução, pausa e cancelamento | Fluxo de estados e confirmações respeita o firmware confirmado |
| 16 | Air assist | Comando confirmado no equipamento; desligamento e erros tratados |
| 17 | Gravação raster | Escala, espaçamento de linhas, direção e algoritmos de imagem comparados |
| 18 | Materiais e matriz de testes | Perfis versionados e parâmetros rastreáveis por máquina/material |
| 19 | Acessório rotativo | Unidades, circunferência e calibração verificadas; perfil separado do plano |
| 20 | Gabaritos e produção em lote | Posicionamento repetível e nomes vinculados às peças corretas |
| 21 | Custos, histórico e backup | Cálculos transparentes, restauração e reabertura de trabalhos |
| 22 | Empacotamento e distribuição | Instalação em ambiente limpo, dados preservados e atribuições incluídas |

## 8. Arquitetura proposta por responsabilidades

Separar módulos, mesmo que inicialmente permaneçam no mesmo repositório:

- **Interface:** painéis, comandos, atalhos e apresentação do estado.
- **Modelo de documento:** objetos, grupos, camadas, unidades e metadados.
- **Geometria:** transformações, medidas, limites e operações de caminhos.
- **Importação/exportação:** formatos e conversões sem dependência do hardware.
- **Planejamento:** trajetórias, ordem, passadas e parâmetros.
- **G-code:** geração específica para o controlador confirmado.
- **Execução:** fila, fluxo de envio, respostas e máquina de estados.
- **Transporte:** comunicação serial e implementação simulada substituível.
- **Persistência:** projetos versionados, materiais, preferências e histórico.

Usar milímetros como unidade interna padrão ou documentar claramente qualquer outra escolha. Diferenciar coordenadas de tela, documento, trabalho e máquina. Transformações e inversões devem ser explícitas e testáveis.

Definir um formato próprio e versionado. Preservar recursos originais necessários para reabrir projetos, evitando depender de caminhos locais quebrados. Leitura direta de projetos do LightBurn é uma melhoria futura de interoperabilidade, não requisito da primeira versão.

Operações pesadas não devem bloquear a interface. A stack e as bibliotecas devem ser escolhidas após a inspeção, e suas licenças precisam permitir a distribuição pretendida.

## 9. Execução e validação física

- Trabalhar por padrão em simulação até haver validação explícita da etapa física.
- Não conectar, iniciar trabalho ou emitir automaticamente ao abrir o aplicativo.
- Confirmar identidade do equipamento e parâmetros antes do primeiro comando de movimento.
- Tratar estados como desconectado, conectado, ocioso, executando, pausando, pausado, cancelando, erro e alarme conforme o protocolo real.
- Diferenciar comando enviado, aceito pelo controlador e movimento concluído.
- Respeitar buffer e controle de fluxo; não confundir velocidade de envio com velocidade de execução.
- Não retomar um trabalho automaticamente após reconexão ou reinicialização.
- Não prometer parada instantânea sem verificar o comportamento do controlador e dos comandos em buffer.
- O botão de parada do aplicativo não substitui parada física de emergência.
- Manter limites de potência e movimento coerentes com o perfil confirmado.
- Fazer primeiro testes de comunicação, depois movimentos com emissão desativada, e somente depois testes graduais de gravação acompanhados pelo usuário.
- Manter registros técnicos sem chaves, dados pessoais ou conteúdo desnecessário dos clientes.

## 10. Melhorias prioritárias para meu trabalho

### Facas e personalizados

- Gabaritos por modelo de faca, medidas e áreas permitidas.
- Posicionamento de nome, logotipo e fachada com distância das bordas.
- Prévia de tamanho real e pontos de referência para alinhamento.
- Alertas visuais quando o desenho sair da área configurada.
- Importação de lista de nomes e associação explícita entre peça e arte.
- Repetição de layouts e organização de pedidos.

### Produção

- Perfis por material com máquina, foco, potência, velocidade, passadas e resultado observado.
- Matrizes de teste configuráveis e registro de fotos opcionais.
- Histórico para repetir um trabalho com os parâmetros originais.
- Estimativa de custo com tempo, material, preparação e margem informados pelo usuário.
- Backup e exportação de projetos e configurações.
- Assistente de primeiro uso e mensagens em português claro.

Essas melhorias entram após suas dependências básicas. Nenhuma deve atrasar a entrega da interface inicial.

## 11. Documentação no repositório

| Arquivo | Conteúdo |
|---|---|
| README.md | Instalação, execução, requisitos e limitações atuais |
| ROADMAP.md | Etapas, dependências e prioridades |
| PROGRESSO.md | Entrega atual, concluído, pendências e próximo passo |
| docs/REFERENCIA.md | Comportamentos observados e fontes públicas |
| docs/REA.md | Identidade da ferramenta, versão, configuração e comandos reais |
| docs/ARQUITETURA.md | Módulos, decisões e sistemas de coordenadas |
| docs/VALIDACAO.md | Casos, resultados, evidências e limitações |
| docs/MAQUINA.md | Controlador, firmware e parâmetros confirmados |
| docs/DEPENDENCIAS.md | Bibliotecas e licenças incorporadas |

Não guardar binários proprietários, chaves ou grandes capturas no repositório por padrão. Guardar somente referências e evidências necessárias e adequadas.

## 12. Modelo de entrega por etapa

Ao encerrar uma etapa, apresentar:

1. **Resultado:** comportamento concreto implementado.
2. **Arquivos alterados:** resumo dos módulos relevantes.
3. **Como executar:** comandos reais e pré-requisitos.
4. **Como verificar:** exemplo reproduzível e resultado esperado.
5. **Validação realizada:** testes efetivamente executados e evidências.
6. **Limitações:** partes simuladas, pendentes e não verificadas.
7. **Próxima etapa:** uma funcionalidade proposta, sem implementá-la ainda.

Atualizar PROGRESSO.md antes de encerrar. Em retomadas, ler o progresso e inspecionar o código para não repetir trabalho nem confiar em marcações desatualizadas.

## 13. Critério de conclusão do produto inicial

O produto inicial estará pronto quando instalar e executar no computador alvo, abrir e salvar projetos, preparar os formatos suportados e realizar um trabalho simples na máquina confirmada com posicionamento, parâmetros e estados verificados. Deverá também tratar desconexão e erro sem retomada automática, ter documentação utilizável e não depender do LightBurn para funcionar.

Paridade ampla com outros controladores, formatos ou recursos avançados será uma evolução posterior, organizada em novas etapas.

## 14. Comando inicial de execução do plano

Comece agora pela inspeção e preparação mínima. Verifique REA e LightBurn, registre o que está realmente disponível e implemente somente a interface da Etapa 1. Não espere ter compreendido todo o programa de referência para entregar a primeira tela. Se faltar acesso visual, solicite uma captura da janela principal e avance no que for independente dela. Ao concluir, apresente a interface e aguarde minha avaliação.
