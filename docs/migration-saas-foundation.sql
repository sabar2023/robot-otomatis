-- =====================================================================
-- BrandBisnis V5.0 - Fondasi SaaS (pelanggan & admin)
-- Jalankan di Supabase SQL Editor pada project "robot otomatis".
-- Idempotent: aman dijalankan ulang.
-- Tidak mengubah strategi sinyal/filter/order live yang sudah backtest.
-- =====================================================================

begin;

-- ------------------------------------------------------------------
-- 1. Perluas users_profile (profil, KYC, paket, peran)
-- ------------------------------------------------------------------
alter table public.users_profile
  add column if not exists nama_akun text,
  add column if not exists role text not null default 'customer',
  add column if not exists kyc_status text not null default 'pending',
  add column if not exists ktp_image_url text,
  add column if not exists selfie_image_url text,
  add column if not exists is_blocked boolean not null default false,
  add column if not exists plan text not null default 'free_trial',
  add column if not exists trial_ends_at timestamptz;

-- ------------------------------------------------------------------
-- 2. Helper: cek admin
-- ------------------------------------------------------------------
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.users_profile p
    where p.auth_id = auth.uid()
      and p.role = 'admin'
      and not p.is_blocked
  );
$$;

-- ------------------------------------------------------------------
-- 3. Kebijakan profil: user hanya dirinya sendiri, admin semua
-- ------------------------------------------------------------------
drop policy if exists "profile_select_own" on public.users_profile;
create policy "profile_select_own"
  on public.users_profile for select to authenticated
  using (auth_id = auth.uid() or public.is_admin());

drop policy if exists "profile_insert_own" on public.users_profile;
create policy "profile_insert_own"
  on public.users_profile for insert to authenticated
  with check (auth_id = auth.uid());

drop policy if exists "profile_update_own" on public.users_profile;
create policy "profile_update_own"
  on public.users_profile for update to authenticated
  using (auth_id = auth.uid() or public.is_admin())
  with check (auth_id = auth.uid() or public.is_admin());

-- ------------------------------------------------------------------
-- 4. Langganan & paket
-- ------------------------------------------------------------------
create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users_profile(id) on delete cascade,
  plan text not null default 'free_trial',
  status text not null default 'active',
  started_at timestamptz not null default now(),
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

alter table public.subscriptions enable row level security;

drop policy if exists "sub_select" on public.subscriptions;
create policy "sub_select"
  on public.subscriptions for select to authenticated
  using (user_id = (select id from public.users_profile where auth_id = auth.uid()) or public.is_admin());

drop policy if exists "sub_insert" on public.subscriptions;
create policy "sub_insert"
  on public.subscriptions for insert to authenticated
  with check (user_id = (select id from public.users_profile where auth_id = auth.uid()) or public.is_admin());

drop policy if exists "sub_update" on public.subscriptions;
create policy "sub_update"
  on public.subscriptions for update to authenticated
  using (public.is_admin());

-- ------------------------------------------------------------------
-- 5. Pembayaran premium (Duitku)
-- ------------------------------------------------------------------
create table if not exists public.payments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users_profile(id) on delete cascade,
  provider text not null default 'duitku',
  reference text,
  amount numeric(18,2) not null default 0,
  status text not null default 'pending',
  paid_at timestamptz,
  created_at timestamptz not null default now()
);

alter table public.payments enable row level security;

drop policy if exists "pay_select" on public.payments;
create policy "pay_select"
  on public.payments for select to authenticated
  using (user_id = (select id from public.users_profile where auth_id = auth.uid()) or public.is_admin());

-- ------------------------------------------------------------------
-- 6. Tiket dukungan + pesan
-- ------------------------------------------------------------------
create table if not exists public.support_tickets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users_profile(id) on delete cascade,
  subject text not null default '',
  status text not null default 'open',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz
);

alter table public.support_tickets enable row level security;

drop policy if exists "ticket_select" on public.support_tickets;
create policy "ticket_select"
  on public.support_tickets for select to authenticated
  using (user_id = (select id from public.users_profile where auth_id = auth.uid()) or public.is_admin());

drop policy if exists "ticket_insert" on public.support_tickets;
create policy "ticket_insert"
  on public.support_tickets for insert to authenticated
  with check (user_id = (select id from public.users_profile where auth_id = auth.uid()));

drop policy if exists "ticket_update" on public.support_tickets;
create policy "ticket_update"
  on public.support_tickets for update to authenticated
  using (user_id = (select id from public.users_profile where auth_id = auth.uid()) or public.is_admin());

create table if not exists public.ticket_messages (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references public.support_tickets(id) on delete cascade,
  sender text not null default 'user',
  message text not null default '',
  image_url text,
  file_url text,
  created_at timestamptz not null default now()
);

alter table public.ticket_messages enable row level security;

drop policy if exists "tmsg_select" on public.ticket_messages;
create policy "tmsg_select"
  on public.ticket_messages for select to authenticated
  using (
    exists (select 1 from public.support_tickets t where t.id = ticket_id)
    and (
      (select user_id from public.support_tickets t where t.id = ticket_id) =
        (select id from public.users_profile where auth_id = auth.uid())
      or public.is_admin()
    )
  );

drop policy if exists "tmsg_insert" on public.ticket_messages;
create policy "tmsg_insert"
  on public.ticket_messages for insert to authenticated
  with check (
    sender = 'user'
    and (select user_id from public.support_tickets t where t.id = ticket_id) =
        (select id from public.users_profile where auth_id = auth.uid())
  );

-- ------------------------------------------------------------------
-- 7. Versi aplikasi (Update Aplikasi)
-- ------------------------------------------------------------------
create table if not exists public.app_versions (
  id uuid primary key default gen_random_uuid(),
  platform text not null default 'android',
  version text not null,
  download_url text,
  release_notes text,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

alter table public.app_versions enable row level security;

drop policy if exists "ver_select" on public.app_versions;
create policy "ver_select"
  on public.app_versions for select to authenticated using (true);

-- ------------------------------------------------------------------
-- 8. Panduan
-- ------------------------------------------------------------------
create table if not exists public.guides (
  id uuid primary key default gen_random_uuid(),
  title text not null default '',
  body text,
  file_url text,
  created_at timestamptz not null default now()
);

alter table public.guides enable row level security;

drop policy if exists "guide_select" on public.guides;
create policy "guide_select"
  on public.guides for select to authenticated using (true);

-- ------------------------------------------------------------------
-- 9. Pengaturan sistem (control plane admin)
-- ------------------------------------------------------------------
create table if not exists public.admin_settings (
  key text primary key,
  value text,
  updated_at timestamptz not null default now()
);

alter table public.admin_settings enable row level security;

drop policy if exists "setting_select" on public.admin_settings;
create policy "setting_select"
  on public.admin_settings for select to authenticated using (true);

drop policy if exists "setting_insert" on public.admin_settings;
create policy "setting_insert"
  on public.admin_settings for insert to authenticated
  with check (public.is_admin());

drop policy if exists "setting_update" on public.admin_settings;
create policy "setting_update"
  on public.admin_settings for update to authenticated
  using (public.is_admin())
  with check (public.is_admin());

-- ------------------------------------------------------------------
-- 10. Nilai default pengaturan sistem (opsional; aman di-upsert)
-- ------------------------------------------------------------------
insert into public.admin_settings (key, value)
values
  ('trading_margin_mode', 'fixed'),
  ('trading_margin_pct', '10'),
  ('trading_tp_pct', '6.0'),
  ('trading_sl_pct', '3.0'),
  ('trading_leverage', '5'),
  ('feature_premium_active', 'true'),
  ('feature_free_active', 'true')
on conflict (key) do nothing;

commit;