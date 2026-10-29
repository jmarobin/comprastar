-- CompraStar: cadastro persistente de parceiros e controle de classificação premium.
-- No projeto Supabase existente, execute este arquivo no SQL Editor.
-- Pode ser executado novamente: as tabelas e políticas são criadas/atualizadas de forma idempotente.

create table if not exists public.supplier_directory (
    id uuid primary key default gen_random_uuid(),
    supplier_key text not null unique,
    name text not null check (length(btrim(name)) between 1 and 200),
    phone_numbers text not null check (length(btrim(phone_numbers)) > 0),
    city text not null check (length(btrim(city)) > 0),
    ddds text not null default '',
    state text not null default 'SC',
    contacts text not null default '',
    category text not null default 'Regular' check (category in ('Regular', 'Premium')),
    whatsapp_numbers text not null default '',
    latitude double precision not null check (latitude between -35 and 6),
    longitude double precision not null check (longitude between -75 and -30),
    created_by uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default now()
);

alter table public.supplier_directory enable row level security;
revoke all on table public.supplier_directory from anon, public;
grant select, insert on table public.supplier_directory to authenticated;

drop policy if exists "authorized CompraStar users can read supplier directory" on public.supplier_directory;
create policy "authorized CompraStar users can read supplier directory"
    on public.supplier_directory for select to authenticated
    using (lower(coalesce(auth.jwt() ->> 'email', '')) in (
        'rhayssa.grassi@starprotecao.com.br',
        'willian.silva@starprotecao.com.br',
        'felipe.cardoso@starprotecao.com.br',
        'gabriel.santos@starprotecao.com.br',
        'maiki.durigon@starprotecao.com.br',
        'joao.andrade@starprotecao.com.br'
    ));

drop policy if exists "only CompraStar managers can add suppliers" on public.supplier_directory;
create policy "only CompraStar managers can add suppliers"
    on public.supplier_directory for insert to authenticated
    with check (
        lower(coalesce(auth.jwt() ->> 'email', '')) in (
            'maiki.durigon@starprotecao.com.br',
            'joao.andrade@starprotecao.com.br'
        )
        and created_by = (select auth.uid())
    );

comment on table public.supplier_directory is
    'Parceiros extras cadastrados por Maiki ou João Marobin pela área de gestão do CompraStar.';

-- Persisted premium decisions. One row per supplier; false can explicitly demote a default premium.
create table if not exists public.supplier_premium_overrides (
    supplier_key text primary key check (length(btrim(supplier_key)) > 0),
    supplier_name text not null check (length(btrim(supplier_name)) between 1 and 200),
    city text not null default '',
    is_premium boolean not null,
    updated_by uuid not null references auth.users(id) on delete restrict,
    updated_at timestamptz not null default now()
);

alter table public.supplier_premium_overrides enable row level security;
revoke all on table public.supplier_premium_overrides from anon, public;
grant select, insert, update on table public.supplier_premium_overrides to authenticated;

drop policy if exists "authorized CompraStar users can read premium statuses" on public.supplier_premium_overrides;
create policy "authorized CompraStar users can read premium statuses"
    on public.supplier_premium_overrides for select to authenticated
    using (lower(coalesce(auth.jwt() ->> 'email', '')) in (
        'rhayssa.grassi@starprotecao.com.br',
        'willian.silva@starprotecao.com.br',
        'felipe.cardoso@starprotecao.com.br',
        'gabriel.santos@starprotecao.com.br',
        'maiki.durigon@starprotecao.com.br',
        'joao.andrade@starprotecao.com.br'
    ));

drop policy if exists "only managers can insert premium statuses" on public.supplier_premium_overrides;
create policy "only managers can insert premium statuses"
    on public.supplier_premium_overrides for insert to authenticated
    with check (
        lower(coalesce(auth.jwt() ->> 'email', '')) in (
            'maiki.durigon@starprotecao.com.br',
            'joao.andrade@starprotecao.com.br'
        )
        and updated_by = (select auth.uid())
    );

drop policy if exists "only managers can update premium statuses" on public.supplier_premium_overrides;
create policy "only managers can update premium statuses"
    on public.supplier_premium_overrides for update to authenticated
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

comment on table public.supplier_premium_overrides is
    'Decisões de status Premium feitas pelos gestores; substituem a classificação padrão calculada pelo app.';
