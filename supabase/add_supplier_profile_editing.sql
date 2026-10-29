-- CompraStar: habilita edição persistente de perfis de parceiros.
-- Execute uma vez no SQL Editor do projeto Supabase existente.
-- Pode ser reexecutado com segurança.

create table if not exists public.supplier_profile_overrides (
    supplier_key text primary key check (length(btrim(supplier_key)) > 0),
    name text not null check (length(btrim(name)) between 1 and 200),
    phone_numbers text not null check (length(btrim(phone_numbers)) > 0),
    city text not null check (length(btrim(city)) > 0),
    ddds text not null default '',
    state text not null default 'SC',
    contacts text not null default '',
    whatsapp_numbers text not null default '',
    latitude double precision not null check (latitude between -35 and 6),
    longitude double precision not null check (longitude between -75 and -30),
    updated_by uuid not null references auth.users(id) on delete restrict,
    updated_at timestamptz not null default now()
);

alter table public.supplier_profile_overrides enable row level security;
revoke all on table public.supplier_profile_overrides from anon, public;
grant select, insert, update on table public.supplier_profile_overrides to authenticated;

drop policy if exists "authorized CompraStar users can read supplier profile overrides"
    on public.supplier_profile_overrides;
create policy "authorized CompraStar users can read supplier profile overrides"
    on public.supplier_profile_overrides for select to authenticated
    using (lower(coalesce(auth.jwt() ->> 'email', '')) in (
        'rhayssa.grassi@starprotecao.com.br',
        'willian.silva@starprotecao.com.br',
        'felipe.cardoso@starprotecao.com.br',
        'gabriel.santos@starprotecao.com.br',
        'maiki.durigon@starprotecao.com.br',
        'joao.andrade@starprotecao.com.br'
    ));

drop policy if exists "only CompraStar managers can insert supplier profile overrides"
    on public.supplier_profile_overrides;
create policy "only CompraStar managers can insert supplier profile overrides"
    on public.supplier_profile_overrides for insert to authenticated
    with check (
        lower(coalesce(auth.jwt() ->> 'email', '')) in (
            'maiki.durigon@starprotecao.com.br',
            'joao.andrade@starprotecao.com.br'
        )
        and updated_by = (select auth.uid())
    );

drop policy if exists "only CompraStar managers can update supplier profile overrides"
    on public.supplier_profile_overrides;
create policy "only CompraStar managers can update supplier profile overrides"
    on public.supplier_profile_overrides for update to authenticated
    using (lower(coalesce(auth.jwt() ->> 'email', '')) in (
        'maiki.durigon@starprotecao.com.br',
        'joao.andrade@starprotecao.com.br'
    ))
    with check (
        lower(coalesce(auth.jwt() ->> 'email', '')) in (
            'maiki.durigon@starprotecao.com.br',
            'joao.andrade@starprotecao.com.br'
        )
        and updated_by = (select auth.uid())
    );

comment on table public.supplier_profile_overrides is
    'Edições persistentes de fornecedores. Somente os gestores do CompraStar podem gravar mudanças.';
