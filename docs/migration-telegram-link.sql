alter table public.user_settings
  add column if not exists telegram_link_token text;