alter table public.user_settings
  add column if not exists margin_mode text not null default 'fixed';