# Manual operacional — Star Compras por placa

## Objetivo

Reduzir o trabalho manual dos compradores: em vez de digitar cada peça e cada preço, registrar um caso por placa/sinistro, colar até cinco orçamentos recebidos e deixar a plataforma extrair e comparar as linhas.

## 1. Abrir o caso

Na tela **Casos por placa**, cadastre placa, número do sinistro, veículo/ano, comprador, região e oficina. Um veículo pode voltar à operação em outro sinistro; nesse caso, abra outro caso para não misturar orçamentos de eventos diferentes.

## 2. Registrar até cinco cotações

Em cada espaço, escolha um fornecedor do cadastro ou digite seu nome, cole a mensagem de WhatsApp como foi recebida e informe frete, condição predominante, prazo e garantia quando disponíveis. Depois, salve o orçamento. Um caso aceita até cinco propostas (opções 1–5).

Exemplo de texto aceito:

```text
RETROVISOR ESO ELETRICO 590
FAROL ESQ 480
FRISO PORTA DIANTEIRA ESQ 150
PARABARRO ESQ 150
PARALAMA ESQ 330
PORTA DIANTEIRA ESQ 1790
```

O sistema interpreta o preço no final de cada linha. Aceita formatos como `590`, `1.790`, `1.790,00` e `R$ 1.790,00`. Frete deve ser lançado no campo de frete, não repetido no texto das peças.

## 3. Conferir a extração

A plataforma exibe linhas interpretadas, subtotal e linhas para revisão. Itens sem um preço final legível não são incluídos no total e aparecem para conferência. Linhas com termos como TOTAL, SUBTOTAL, FRETE, ENTREGA ou PRAZO são isoladas para evitar dupla contagem, e não adicionadas ao subtotal das peças.

A normalização ajuda a agrupar grafias comuns (por exemplo, acentos, hífens, ESQ/ESQUERDO e PARA-LAMA/PARALAMA), mas não comprova que peças com nomes semelhantes sejam tecnicamente idênticas. Confira posição/lado, marca, código, condição e compatibilidade. Se dois fornecedores usarem descrições muito diferentes para a mesma peça, o comprador deve revisar a matriz; o sistema não deve ser tratado como validador técnico.

## 4. Como interpretar a comparação

- **Total do orçamento:** soma das linhas interpretadas + frete informado.
- **Cobertura:** proporção de descrições de peças encontradas naquela proposta frente ao total de descrições identificadas em todas as cotações daquele caso.
- **Peças faltantes:** descrições identificadas em outras propostas que não apareceram naquela proposta.
- **Menor preço por peça:** menor valor registrado entre linhas com a mesma descrição normalizada.
- **Menor total com cobertura completa:** destaque apenas quando existe proposta que cobre todas as descrições identificadas. Se nenhuma cobre, não compare só o total bruto; revise os itens faltantes.
- **Gap de escolha:** diferença entre a proposta selecionada e a menor proposta que cobre o mesmo conjunto de peças. É oportunidade estimada, não economia realizada.

## 5. Escolha e acompanhamento

Registre a opção escolhida e o motivo (menor total com cobertura completa, prazo, disponibilidade, qualidade, garantia ou condição comercial). Depois atualize status, data do pedido, data prevista, data real e custo efetivamente pago. Registre problemas de entrega ou qualidade nas ocorrências.

## 6. Cadastro de fornecedores

Na tela **Fornecedores**, mantenha regiões atendidas, categorias, qualidade percebida (1–5), confiabilidade (1–5), condições comerciais, contato e notas objetivas. A pontuação é uma avaliação interna da equipe; não é garantia de qualidade.

Também é possível preencher `modelo_fornecedores_star.xlsx` e importar o arquivo pela própria plataforma. Fornecedores com o mesmo nome são atualizados; por isso, use nomenclatura consistente.

## 7. Rotina de coordenação

- **Diariamente:** revisar casos com poucas propostas, linhas não interpretadas e entrega em atraso.
- **Semanalmente:** analisar diferenças de preço por peça, cobertura regional, motivos de escolha e ocorrências por fornecedor.
- **Mensalmente:** comparar custo por caso em perfis semelhantes, evolução de preços e condições negociadas. Não atribua toda mudança no ticket médio ao comprador: gravidade, veículo e quantidade de peças podem variar.

## Segurança e limitações

A versão inicial usa banco SQLite local e não tem login, controle de permissões nem trilha de alterações. Antes do uso compartilhado com dados reais, implante autenticação, perfis, auditoria e backup corporativo. Evite incluir dados pessoais de associados que não sejam necessários para a compra.
