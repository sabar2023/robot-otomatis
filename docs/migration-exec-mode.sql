alter table public.user_settings
  add column if not exists exec_mode text not null default 'demo';