# Localizador de Parceiros — Autopeças

Aplicação em Streamlit que permite ao comprador digitar uma cidade e visualizar autopeças parceiras em um raio de até 100 km.

## O que já faz

- Campo de busca por cidade (aceita cidades da base e tenta geocodificar outras cidades brasileiras).
- Raio ajustável de 25 a 100 km.
- Mapa interativo com a cidade pesquisada, o círculo do raio e marcadores das autopeças.
- Clique em um marcador para abrir o cartão do parceiro com nome, cidade, telefones e links para ligação/WhatsApp quando o formato do número permitir.
- Lista de parceiros ordenada por distância aproximada.
- Área de revisão para cadastros cuja cidade está ambígua ou não foi reconhecida.
- Filiais da Peças CJ e da Peças Krambeck distribuídas por cada cidade cadastrada, com contatos agrupados por loja.
- Peças Jota e Peças Jota Joel unificadas em uma única ficha, sem repetir números, preservando a identificação de Joel nos telefones correspondentes.
- Auto Peças Padova posicionada em Arvoredo/SC.

## Como rodar no computador

1. Instale Python 3.11 ou superior.
2. Extraia a pasta do projeto.
3. Abra o terminal dentro da pasta `localizador_parceiros`.
4. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

5. Inicie o app:

   ```bash
   streamlit run app.py
   ```

## Como publicar pelo GitHub + Streamlit Community Cloud

1. Entre no GitHub e crie um repositório. Para uso interno, escolha privado e confirme as regras de acesso antes de publicar os contatos.
2. Envie todos os arquivos e pastas deste projeto para o repositório, mantendo `app.py`, `requirements.txt`, `city_coords.py`, a pasta `data/` e `.streamlit/`.
3. Entre em [Streamlit Community Cloud](https://share.streamlit.io/) e conecte a conta do GitHub.
4. Clique em **Create app**, selecione o repositório e informe `app.py` como arquivo principal.
5. Clique em **Deploy**. As dependências são instaladas pelo `requirements.txt`.

## Atualizar a lista de parceiros

O arquivo `data/parceiros.csv` é separado por ponto e vírgula (`;`) e está em UTF-8. Para incluir ou alterar um parceiro, atualize esse arquivo e envie a alteração ao GitHub. Preserve as colunas `Nome`, `Números`, `Cidade`, `DDD(s)`, `UF provável pelo DDD` e `Contatos`. A coluna opcional `Contatos` usa o formato `Nome do contato: número; Outro contato: número` para diferenciar os telefones de uma mesma loja.

A coluna **Cidade** deve conter preferencialmente um único município por registro. As lojas da Peças CJ e da Peças Krambeck já estão separadas em registros individuais por cidade. Para os demais parceiros, use preferencialmente um município por registro.

## Observações importantes

- A distância é calculada em linha reta entre o centro aproximado do município pesquisado e o centro aproximado do município parceiro. Não é distância por estrada nem localização exata do estabelecimento.
- Para cidades que não estão na lista de coordenadas usada pela base, a aplicação tenta consultar o serviço público Nominatim/OpenStreetMap. Essa função depende de conexão à internet.
- Se o app ficar público, os dados de contato que aparecem nele poderão ser vistos por quem tiver acesso ao app. Revise as configurações de acesso e a autorização para compartilhar os telefones antes de publicar.
- A base foi reorganizada a partir da planilha recebida: CJ e Krambeck aparecem em cada cidade informada; Jota e Jota Joel foram consolidados; Padova foi corrigida para Arvoredo. As coordenadas são aproximadas do centro dos municípios, não o endereço exato das lojas.

### Ajustes recentes do layout e contatos

- Tema escuro, mapa escuro e barra superior do Streamlit ocultada no layout.
- Busca de cidades com autocomplete fuzzy (por exemplo, `itaj` sugere `Itajaí`) e opção de digitar uma cidade não listada.
- Links do WhatsApp aparecem para números com padrão de celular brasileiro. Telefones fixos ou outros números sem padrão de WhatsApp ficam em texto selecionável para copiar.
- Números duplicados na mesma ficha são normalizados, inclusive variantes antigas de celular com 8 dígitos.
- Rodapé `Powered by Marobin Group`.
- A lista de parceiros mostra cidade e distância; os telefones são apresentados nas fichas, evitando expor números repetidos na tabela.
