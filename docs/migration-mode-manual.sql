alter table public.user_settings
  add column if not exists mode_manual boolean not null default false;