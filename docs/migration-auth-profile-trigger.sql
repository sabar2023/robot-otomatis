-- Auto-buat users_profile saat auth user baru terdaftar (metadata registrasi).
-- Disclaimer: tidak mengubah strategi sinyal/order live.
begin;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.users_profile (
    auth_id, email, nama, nama_akun, no_hp,
    role, kyc_status, plan, trial_ends_at
  )
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'nama_lengkap', split_part(new.email, '@', 1)),
    new.raw_user_meta_data->>'nama_akun',
    new.raw_user_meta_data->>'no_hp',
    'customer',
    case
      when coalesce(new.raw_user_meta_data->>'nama_lengkap', '') <> ''
       and coalesce(new.raw_user_meta_data->>'nama_akun', '') <> ''
       and coalesce(new.raw_user_meta_data->>'no_hp', '') <> ''
      then 'verified' else 'pending'
    end,
    'free_trial',
    now() + interval '7 days'
  )
  on conflict (auth_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

commit;