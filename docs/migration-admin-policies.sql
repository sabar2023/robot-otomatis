-- Kebijakan admin: CRUD panduan, versi aplikasi, tiket, dan balasan tiket.
-- Disclaimer: tidak mengubah strategi sinyal/order live.
begin;

drop policy if exists "guide_insert" on public.guides;
create policy "guide_insert" on public.guides for insert to authenticated
  with check (public.is_admin());

drop policy if exists "guide_update" on public.guides;
create policy "guide_update" on public.guides for update to authenticated
  using (public.is_admin()) with check (public.is_admin());

drop policy if exists "guide_delete" on public.guides;
create policy "guide_delete" on public.guides for delete to authenticated
  using (public.is_admin());

drop policy if exists "ver_insert" on public.app_versions;
create policy "ver_insert" on public.app_versions for insert to authenticated
  with check (public.is_admin());

drop policy if exists "ver_update" on public.app_versions;
create policy "ver_update" on public.app_versions for update to authenticated
  using (public.is_admin()) with check (public.is_admin());

drop policy if exists "ver_delete" on public.app_versions;
create policy "ver_delete" on public.app_versions for delete to authenticated
  using (public.is_admin());

drop policy if exists "ticket_delete" on public.support_tickets;
create policy "ticket_delete" on public.support_tickets for delete to authenticated
  using (public.is_admin());

drop policy if exists "tmsg_insert_admin" on public.ticket_messages;
create policy "tmsg_insert_admin" on public.ticket_messages for insert to authenticated
  with check (sender = 'admin' and public.is_admin());

drop policy if exists "tmsg_update" on public.ticket_messages;
create policy "tmsg_update" on public.ticket_messages for update to authenticated
  using (public.is_admin());

drop policy if exists "tmsg_delete" on public.ticket_messages;
create policy "tmsg_delete" on public.ticket_messages for delete to authenticated
  using (public.is_admin());

commit;