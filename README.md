# Star Compras — Orçamentos por placa

Aplicação independente em Streamlit para registrar um caso por placa/sinistro, colar até cinco orçamentos recebidos por WhatsApp, extrair os preços automaticamente, comparar cobertura e valores por peça e acompanhar fornecedor, decisão e entrega.

## Funcionalidades

- Cadastro de caso por placa, com sinistro, veículo, comprador, região e oficina.
- Até cinco espaços de orçamento por caso.
- Colagem do texto como recebido do WhatsApp, com extração do preço no final de cada linha.
- Soma automática das linhas interpretadas + frete informado.
- Comparação das descrições normalizadas entre fornecedores e identificação do menor valor por item.
- Cobertura de peças por orçamento, peças que faltam e destaque de proposta com cobertura completa.
- Conferência explícita de linhas não interpretadas e linhas tratadas como totais/frete/observações.
- Cadastro de fornecedores por região, categorias, qualidade percebida, confiabilidade e condições comerciais.
- Importação de cadastro de fornecedores por Excel/CSV e modelo Excel para preenchimento.
- Registro do fornecedor selecionado, justificativa, status do pedido, previsão/entrega real e custo final.
- Dashboard gerencial e exportação de casos, orçamentos, itens interpretados e fornecedores.

## Rodar no computador

Requer Python 3.10 ou mais recente.

```bash
python -m venv .venv
```

Windows:
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux:
```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

O banco `data/star_compras_placas.db` é criado automaticamente na primeira execução. Faça backup periódico desse arquivo.

## Como funciona a extração

O comprador escolhe o fornecedor, cola o texto e salva. Linhas como `FAROL ESQ 480` ou `PORTA DIANTEIRA ESQ 1.790,00` são interpretadas como descrição + valor no fim da linha. Acentos, hífens e abreviações comuns são normalizados para facilitar a conferência. Linhas sem preço final ou com formato inesperado ficam em uma seção de revisão e não entram silenciosamente no subtotal.

A aplicação não usa IA externa para ler as cotações; a extração é feita por regras locais. Formatos novos devem ser testados. O frete deve ser informado no campo próprio. Linhas que começam com TOTAL, SUBTOTAL, FRETE, ENTREGA ou PRAZO são isoladas para evitar dupla contagem, mas devem ser conferidas.

## Importante antes de usar com dados reais da Star

Esta é uma primeira versão para validar o fluxo. Usa SQLite local, sem login, perfis de acesso, trilha de auditoria ou sincronização multiusuário robusta. Antes de uso corporativo, implementar autenticação, permissões, auditoria, backup e armazenamento corporativo persistente. Não use um banco SQLite local em hospedagem efêmera sem política de persistência.

A comparação por peça depende das descrições fornecidas. O sistema normaliza grafias comuns, mas não garante equivalência técnica entre peças. Confirme lado/posição, código, condição, marca e compatibilidade do veículo. O menor total só é comparável quando as propostas cobrem o mesmo conjunto de peças e condições adequadas.

O indicador de gap é uma oportunidade estimada contra a menor proposta com cobertura completa; não deve ser apresentado como economia realizada. O custo final é registrado separadamente.
