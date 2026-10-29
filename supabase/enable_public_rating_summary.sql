-- CompraStar: permitir exibir estrelas e quantidade de avaliações nos cartões públicos.
-- A view expõe somente média, quantidade e nome do fornecedor; não expõe votos individuais nem IDs.
-- Execute uma única vez no SQL Editor do Supabase já configurado.
GRANT SELECT ON TABLE public.supplier_rating_summary TO anon, authenticated;
