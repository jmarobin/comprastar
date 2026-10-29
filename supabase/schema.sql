-- CompraStar: avaliações persistentes de fornecedores.
-- Execute uma vez no SQL Editor do seu projeto Supabase.
-- A regra principal é garantida no banco, não apenas na interface.

create table if not exists public.supplier_ratings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    supplier_key text not null,
    supplier_name text not null,
    rating smallint not null check (rating between 1 and 5),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Esta restrição é a defesa final contra votos repetidos, inclusive requisições simultâneas.
create unique index if not exists supplier_ratings_one_vote_per_buyer_supplier
    on public.supplier_ratings (user_id, supplier_key);

alter table public.supplier_ratings enable row level security;

revoke all on table public.supplier_ratings from anon, public;
grant select, insert, update on table public.supplier_ratings to authenticated;

-- Cada usuário só consegue consultar e editar a própria nota.
drop policy if exists "buyers can read own supplier ratings" on public.supplier_ratings;
create policy "buyers can read own supplier ratings"
    on public.supplier_ratings
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "buyers can insert own supplier ratings" on public.supplier_ratings;
create policy "buyers can insert own supplier ratings"
    on public.supplier_ratings
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "buyers can update own supplier ratings" on public.supplier_ratings;
create policy "buyers can update own supplier ratings"
    on public.supplier_ratings
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

-- Mesmo se uma requisição tentar informar outro user_id, o banco usa o usuário autenticado.
create or replace function public.guard_supplier_rating()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if (select auth.uid()) is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    if tg_op = 'UPDATE' then
        -- Um usuário não pode mover a própria avaliação para outra conta ou ficha de fornecedor.
        new.user_id := old.user_id;
        new.supplier_key := old.supplier_key;
        new.created_at := old.created_at;
    else
        new.user_id := (select auth.uid());
        new.supplier_key := pg_catalog.lower(pg_catalog.btrim(new.supplier_key));
        new.created_at := pg_catalog.now();
    end if;
    new.supplier_name := pg_catalog.left(pg_catalog.btrim(new.supplier_name), 200);
    if new.supplier_key = '' or new.supplier_name = '' then
        raise exception 'Supplier key and name are required' using errcode = '22023';
    end if;
    if new.rating < 1 or new.rating > 5 then
        raise exception 'Rating must be from 1 to 5' using errcode = '22023';
    end if;
    new.updated_at := pg_catalog.now();
    return new;
end;
$$;

revoke all on function public.guard_supplier_rating() from public, anon, authenticated;
drop trigger if exists guard_supplier_rating_before_write on public.supplier_ratings;
create trigger guard_supplier_rating_before_write
    before insert or update on public.supplier_ratings
    for each row execute function public.guard_supplier_rating();

-- Esta view expõe somente médias e quantidade de notas, nunca o ID ou e-mail dos avaliadores.
-- Por padrão, views PostgreSQL executam com as permissões do proprietário; isso permite agregar
-- todas as avaliações mesmo com RLS na tabela-base. A view não inclui dados individuais.
create or replace view public.supplier_rating_summary as
select
    supplier_key,
    max(supplier_name) as supplier_name,
    round(avg(rating)::numeric, 1) as average_rating,
    count(*)::integer as rating_count
from public.supplier_ratings
group by supplier_key;

revoke all on table public.supplier_rating_summary from anon, public;
-- Public sees only aggregated averages and counts, never individual votes or user IDs.
grant select on table public.supplier_rating_summary to anon, authenticated;

comment on table public.supplier_ratings is
    'Uma nota ativa por comprador e fornecedor. Atualizações substituem a nota existente.';
