# CompraStar v19 — edição de perfis de fornecedores

- Gestão reunida em uma única área “Adicionar parceiro / Editar parceiro existente”.
- Seleção de fornecedor existente carrega os dados no formulário para editar nome, cidade, estado, DDD, contatos, telefones e WhatsApp.
- A classificação Regular/Premium fica no mesmo formulário; só os gestores autorizados podem gravá-la.
- Alterações de perfis ficam persistidas em `supplier_profile_overrides` e são aplicadas sobre a base CSV e o diretório do Supabase.
- A chave estável do fornecedor é preservada para não romper as avaliações que já existam.
- Descrição da área de gestão: “Área exclusiva para gestores. Cadastros e classificações são salvos no Supabase e compartilhados com a equipe.”
- Incluído `supabase/add_supplier_profile_editing.sql` e cópia na raiz para habilitar a edição no banco Supabase existente.
