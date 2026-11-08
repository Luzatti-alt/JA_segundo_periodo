### Pegada de carbono em geral(expandir mais isso)

A pegada de um produto é a soma das emissões de gases de efeito estufa ao longo do ciclo de vida, em kg de CO₂e. Todo cálculo, qualquer que seja a metodologia, repousa em três coisas:

- **Fronteira:** o que entra no cálculo (berço ao portão, berço ao túmulo etc.).
- **Dado de atividade:** massa, kWh, litros, t·km.
- **Fator de emissão:** quanto cada unidade emite.
calculo atual em desenvolvimento


### Exemplos do exterior(estudar mais sobre isso)
**Catena-X (automotivo europeu).** Tem um manual de cálculo de pegada (PCF Rulebook), alinhado com ISO 14067( ), GHG Protocol e o PACT da WBCSD( ),é mais um padrão de troca de dados e um processo de verificação, permite trocar dados mesmo quando o dado primário ainda não existe, as emissões da cadeia de suprimentos dominam a pegada automotiva, principalmente com a eletrificação

**Regulamento europeu de baterias (2023/1542).** Exige declaração de pegada de carbono por modelo de bateria e por fábrica, acessível por QR code a partir de 18 de fevereiro de 2027. Também pede dado primário específico da planta, verificado por terceiro

**Brasil.** Existe o SICV Brasil, banco nacional de inventários de ciclo de vida do IBICT, com um guia de qualidade (Qualidata) para os dados que entram

### questão da bateria
**Política Nacional de Circularidade das Baterias Veiculares (PNCBV)**-> **PL 2.132/2025** conjunto de regras e diretrizes voltadas para planejar e incentivar a reutilização, rastreabilidade e reciclagem de baterias de veículos elétricos e híbridos no Brasil
Regulamento europeu de baterias (2023/1542) -> declaração de pegada de carbono por modelo de bateria e por fábrica, acessível por QR code a partir de 18 de fevereiro de 2027
### mudança na ideia(só o conceito protótipo por conta de tempo ficara em um escopo menor)
ideia antiga: uma calculadora de fim de vida, com banco de dados de um veículo de referência

refatorando a ideia: **uma plataforma de pegada de carbono de produto**(mais como prototipo em escopo menor) feito para o perfil automotivo para o MOVER, que guarda dados neutros, calcula por métodos plugáveis e deixa tudo auditável.

mapa de fatores por categoria, cada um com sua fonte e uma hierarquia de qualidade (dado medido na planta, depois dado do fornecedor, depois dado nacional, depois dado internacional adaptado, por fim valor padrão), os fatores principais são **Eletricidade:*(a Renault utiliza fotovoltaica então é algo limpo), Combustíveis:**,**Transporte, materiais e resíduos**(esses três para um calculo mais preciso precisamos definir fatores )

- entender mais sobre rota 2030, MOVER e o MOVER com a reforma tributaria

contexto atual: 31 de dezembro de 2026 as empresas apresentam ao MDIC (o inventário de carbono das plantas e o registro da pegada dos veículos), a partir de 2027 os automóveis de passeio precisam ter ao menos 80% de materiais reutilizáveis ou recicláveis (85% em projetos novos e para todos em 2030).

Rota 2030, programa criado em 2018, pela Lei nº 13.755/2018, para estimular a competitividade do setor automotivo brasileiro durante um ciclo de 15 anos, a rota 2030 se relaciona com a eficiência energética e à segurança dos veículos comercializados no país.

Seus objetivos incluíam:
- Melhorar a eficiência energética dos veículos.
- Aumentar a segurança dos automóveis.
- Incentivar pesquisa, desenvolvimento e inovação (PD&I).
- Modernizar a cadeia produtiva automotiva.
- Aumentar a competitividade da indústria brasileira no mercado internacional.

MOVER também conhecida como Mobilidade Verde e Inovação foi instituído pela Lei nº 14.902/2024, sendo o sucessor da rota Rota 2030 dando destaque sobre a descarbonização, sustentabilidade e novas tecnologias, o mover não é somente para carros elétricos, e também focam em carros a combustão mais eficiente

- Eles já tem o inventário de emissões da planta podemos fazer estimativa com isso com o veiculo saindo da fabrica

cálculos atuais:

Emissão reciclagem (0) + emissão de recuperação + emissão landfill + emissão transporte (padronizado?)

ou 

massa veicuilo*(1-OEM input)*fator emissão landfill + 0,018

1. **Núcleo de dados:** produto, peças, materiais, processos e fatores, cada fator com sua fonte e o nível de qualidade (medido na planta, fornecedor, nacional, internacional adaptado, padrão).
2. **Motor de métodos:** o perfil MOVER/AEA primeiro (WG1 a WG4), com espaço para outros depois.
3. **Governança:** fluxo de aprovação, evidências anexadas, histórico de alterações e pacote de auditoria.
4. **Entradas e saídas:** importação da ficha da desmontadora e da lista de materiais, fatores automáticos (SIN mensal), relatórios e comparação entre métodos

padronizar os cálculos entre empresas, mesmo quando elas usam sistemas diferentes e ainda não possuem dados primários brasileiros suficientesfi