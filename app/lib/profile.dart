import 'package:supabase_flutter/supabase_flutter.dart';

String signalAccess(Map<String, dynamic> prof) {
  final role = (prof["role"] ?? "customer").toString();
  if (role == "admin") return "premium";
  if ((prof["is_blocked"] ?? false) == true) return "blocked";
  final plan = (prof["plan"] ?? "free_trial").toString();
  if (plan == "premium") return "premium";
  if (plan == "free_trial" || plan == "free") {
    final trial = prof["trial_ends_at"];
    if (trial != null && trial.toString().isNotEmpty) {
      try {
        final ends = DateTime.parse(trial.toString());
        if (DateTime.now().isBefore(ends)) return "trial";
      } catch (_) {}
    }
    return "expired";
  }
  return "expired";
}

Future<String> fetchSignalAccess() async {
  final client = Supabase.instance.client;
  final session = client.auth.currentSession;
  if (session == null) return "expired";
  final uid = session.user.id;
  final prof = await client
      .from("users_profile")
      .select("role,plan,trial_ends_at,is_blocked")
      .eq("auth_id", uid)
      .maybeSingle();
  if (prof == null) return "expired";
  return signalAccess(prof);
}

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
