# Star Compras — Gestão de peças e fornecedores

Aplicação independente em Streamlit para acompanhar comparações de preço por peça, fornecedores, decisões de compra, pedidos, prazos, custo efetivo e indicadores gerenciais.

## Funcionalidades

- Cadastro de uma comparação por peça necessária em cada sinistro.
- Registro de várias ofertas por peça, com preço unitário, frete, outros custos, marca, condição, disponibilidade, prazo, garantia e pagamento.
- Seleção de oferta com justificativa e comparação de custo total.
- Acompanhamento do pedido, previsão, entrega, valor final, devoluções e problemas.
- Painel de gastos selecionados, preço histórico de referência, gap de escolha, quantidade de cotações e visão por comprador/categoria.
- Cadastro de fornecedores e resumo de desempenho.
- Exportação da base para Excel.
- Manual operacional incorporado à aplicação.

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

O banco `data/star_compras.db` é criado automaticamente na primeira execução. Faça backup periódico desse arquivo.

## Importante antes de usar com dados reais da Star

Esta é uma primeira versão funcional para validação do processo. O banco é SQLite local, sem login, perfis de acesso, trilha de auditoria nem sincronização confiável para vários servidores. Um banco local pode ser compartilhado entre sessões que acessam o mesmo arquivo/servidor, mas isso não substitui uma arquitetura corporativa persistente.

Antes de publicar com dados reais, configure autenticação, permissões e armazenamento persistente (por exemplo, PostgreSQL gerenciado), além de políticas de backup, proteção e retenção de dados. Em hospedagens com sistema de arquivos efêmero, o banco local pode ser perdido após reinicializações ou novas implantações.

Os cálculos de economia dependem de cotações corretamente cadastradas, comparação de peças tecnicamente equivalentes e referências históricas confiáveis. O indicador "gap de escolha" representa oportunidade identificada, não economia realizada. O painel não substitui a validação técnica, comercial ou contratual da Star.

## Próximas evoluções recomendadas

1. Importação assistida dos dados do sistema atual.
2. Login, perfis de coordenador/comprador e trilha de alterações.
3. Banco de dados corporativo compartilhado e backups automáticos.
4. Regras de aprovação por valor e exceções justificadas.
5. Histórico de preço por código/peça com equivalência técnica validada.
