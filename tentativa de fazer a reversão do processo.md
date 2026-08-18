fluxo provável de funcionamento
![[fluxo_squadro_provavel.png]]
Provável que **não exista nada formal ainda** sobre metodologias ageis nisso o setor de móveis planejados tradicionalmente roda o fluxo de projeto em cima de planilha + WhatsApp + e-mail, sem quadro Kanban, sprints e outras implementações de metodologias ageis, isso bate exatamente com os "gargalos" que o desafio cita (má distribuição de atividades, baixa produtividade, tempo de resposta alto),não é algo que comum em empresas desse porte, a menos que tenham um setor de TI/PMO 

da para dividir em duas partes principais com as ideias soltas:
- **Frente 1 – Gestão do fluxo de projeto (ágil/Kanban)**: atacar diretamente o gargalo da fila de projetistas e retrabalho de revisão. Alta chance de ser 100% novo pra eles.
- **Frente 2 – Notificação automática ao cliente pós-produção**: depende de existir ERP com API de status de produção. Se existir, é "conectar dois pontos que já existem, mas nunca foram ligados" — pitch forte porque é baixo esforço, alto impacto percebido pelo cliente.

parte mais tecnica da frente 2

API do Promob swagger para integrações com o software principal deles -> [[https://api-hub.promob.com/swagger/index.html]], porem ver se  eles ja tem alguma aplicação **ERP**(Enterprise Resource Planning) prorpia com o software/implementar a nossa solução com a erp atual deles (Promob ↔ ERP/CRM)

uso da api propria -> apos movel ficar pronto irria notificar o cliente