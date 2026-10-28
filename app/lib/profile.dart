import 'package:supabase_flutter/supabase_flutter.dart';

Future<String?> ensureProfile() async {
  final client = Supabase.instance.client;
  final session = client.auth.currentSession;
  if (session == null) return null;
  final uid = session.user.id;
  var prof = await client.from("users_profile").select("*").eq("auth_id", uid).maybeSingle();
  if (prof == null) {
    final email = (session.user.email ?? "").toString();
    prof = await client
        .from("users_profile")
        .insert({
          "auth_id": uid,
          "email": email,
          "nama": email.split("@").first,
          "no_hp": "",
        })
        .select()
        .single();
  }
  final idRaw = prof["id"];
  if (idRaw == null) return null;
  return idRaw.toString();
}
