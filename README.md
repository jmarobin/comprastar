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
