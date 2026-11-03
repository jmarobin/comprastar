# CompraStar — versão 20

- Substituída a lista manual limitada de cidades por um catálogo geográfico completo dos 1.191 municípios do Paraná, Rio Grande do Sul e Santa Catarina.
- O catálogo carrega nome, UF e coordenadas municipais aproximadas a partir de CSV público com códigos IBGE, é validado por contagem estadual e armazenado em cache por 30 dias.
- Busca por prefixos sem acento mantida; `itaj` continua resolvendo para Itajaí.
- Cidades homônimas são diferenciadas pela UF no autocomplete e na resolução da busca.
- Parceiros do CSV e do Supabase passam a ser associados ao município usando também a UF, evitando coordenadas incorretas para nomes iguais.
- Fallback de geocodificação também considera a UF quando informada.
- Nenhuma alteração no banco de dados, avaliações, acessos ou Secrets do Supabase.
