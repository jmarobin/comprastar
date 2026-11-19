# CompraStar — Localizador de Parceiros

## Atualização desta versão: busca completa de municípios do PR, RS e SC

A busca agora carrega o catálogo geográfico completo dos três estados, incluindo nome, UF e coordenadas aproximadas do centro municipal. O catálogo é validado antes de ser usado e mantido em cache por 30 dias.

Cobertura validada pelo código: **1.191 municípios** — Paraná (399), Rio Grande do Sul (497) e Santa Catarina (295). Quando houver municípios homônimos, o campo de busca apresenta a UF (por exemplo, `Bom Jesus - RS`) para evitar escolher a cidade errada. Prefixos sem acento continuam aceitos; por exemplo, `itaj` resolve para Itajaí.

### Fonte e conectividade

O aplicativo baixa o CSV geográfico do repositório público `kelvins/municipios-brasileiros` (com espelhos de contingência), que publica códigos IBGE e coordenadas dos municípios. É necessário que o ambiente do Streamlit Cloud tenha acesso de saída ao GitHub no primeiro carregamento e na renovação mensal do cache. Se os três endereços estiverem indisponíveis, o aplicativo mantém a lista anterior de cidades e mostra um aviso; a busca completa será retomada quando o catálogo puder ser carregado.

As coordenadas representam referências municipais aproximadas, não endereços físicos de cada fornecedor. O cálculo do raio permanece em linha reta entre os centros dos municípios.

## Instalação / atualização

1. Extraia todos os arquivos deste ZIP.
2. Substitua no repositório GitHub os arquivos e pastas pelos desta versão, preservando a estrutura.
3. O Streamlit Community Cloud instalará as dependências de `requirements.txt` e reiniciará o aplicativo.
4. Não é necessário executar SQL novo no Supabase nem alterar os Secrets existentes.

## Componentes principais

- `app.py`: aplicativo Streamlit, autenticação, mapa, busca, avaliações e gestão.
- `city_coords.py`: coordenadas de fallback e aliases já conhecidos.
- `data/parceiros.csv`: base local de parceiros.
- `logo_comprastar.png`: identidade visual.
- `supabase/`: scripts de banco de dados já usados nas versões anteriores.

## Teste manual recomendado após publicar

- Digitar `itaj` e pressionar Enter: deve completar para Itajaí.
- Pesquisar municípios menores, como Abatiá (PR), Alto Alegre (RS) e Águas Mornas (SC).
- Se aparecer um nome repetido em mais de um estado, escolher a sugestão com a UF correta.
- Confirmar que o mapa centraliza na cidade escolhida e calcula os fornecedores dentro do raio selecionado.

## Atualização da base de contatos (v21)

A base `data/parceiros.csv` foi revisada a partir do arquivo enviado pela equipe. Celulares em formato brasileiro recebem link WhatsApp; telefones fixos só recebem link quando constam explicitamente na coluna `WhatsApp(s)`. Telefones sem link aparecem como texto copiável. Não é possível confirmar automaticamente se um número possui conta ativa no WhatsApp.


## Versão 22 — nova identidade visual

O cabeçalho foi ajustado para a nova logo vertical STAR Proteção Veicular Total. A imagem é exibida sem distorção, com transparência preservada e tamanhos responsivos para desktop e celular. O botão da logo continua limpando a cidade pesquisada e retornando à visão inicial. A base `data/parceiros.csv` foi atualizada com o arquivo de contatos mais recente fornecido pela equipe.

## Versão 23 — pesquisa por fornecedor

Foi adicionada uma caixa de pesquisa direta por nome do fornecedor, independente da cidade de referência e do raio do mapa. A pesquisa ignora acentos, maiúsculas/minúsculas e a ordem dos termos, permitindo, por exemplo, localizar "Peças Krambeck" digitando `krambeck`, `pecas krambeck` ou `krambeck pecas`.

Os resultados mostram a cidade e a UF, telefones copiáveis, links de WhatsApp configurados, classificação Premium e média/quantidade de avaliações. Até oito fichas aparecem inicialmente; os demais resultados podem ser expandidos. A busca exige login, como o restante do CompraStar. Clicar na logo STAR limpa também essa pesquisa e volta à visão inicial.

Não há migração SQL nem alteração dos Secrets para esta atualização.


## Versão 24 — organização da tela inicial

- Botão de Gestão no cabeçalho, visível apenas para gestores, que abre/fecha o painel de gestão no início da página.
- Removido o expander de gestão da área inferior; o painel é controlado pelo botão do cabeçalho.
- Pesquisa por fornecedor posicionada acima da pesquisa por cidade.
- Títulos de seções padronizados em tamanho, peso, cor e espaçamento.
- A descrição da área de gestão foi mantida exatamente como solicitado.


## Versão 24 — layout reorganizado

- O botão **Gestão** fica no cabeçalho ao lado do título e aparece somente para Maiki e João Marobin.
- O botão abre/fecha o painel de gestão no início da área de trabalho; o antigo expander inferior foi removido.
- A pesquisa por fornecedor aparece antes da pesquisa por cidade.
- Os títulos de seção usam um padrão consistente de tamanho, peso, cor e espaçamento.
- A sessão de gestão é fechada ao sair ou quando um usuário sem perfil de gestor entra.
