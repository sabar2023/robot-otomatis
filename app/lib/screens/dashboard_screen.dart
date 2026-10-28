import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _client = Supabase.instance.client;
  String? _profileId;
  String? _email;
  final _nama = TextEditingController();
  final _hp = TextEditingController();
  final _coins = TextEditingController();
  final _lev = TextEditingController(text: "10");
  final _margin = TextEditingController(text: "10");
  final _tp = TextEditingController();
  final _sl = TextEditingController();
  final _api = TextEditingController();
  final _sec = TextEditingController();
  final _tg = TextEditingController();
  bool _mode = false;
  bool _loaded = false;
  bool _busy = false;
  String? _msg;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final session = _client.auth.currentSession;
      final uid = session?.user.id;
      if (uid == null) return;
      var prof = await _client.from("users_profile").select("*").eq("auth_id", uid).maybeSingle();
      if (prof == null) {
        final email = (session!.user.email ?? "").toString();
        prof = await _client
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
      final pid = idRaw?.toString();
      _profileId = pid;
      if (pid == null) return;
      _email = (prof["email"] ?? "").toString();
      _nama.text = (prof["nama"] ?? "").toString();
      _hp.text = (prof["no_hp"] ?? "").toString();
      final st = await _client.from("user_settings").select("*").eq("user_id", pid).maybeSingle();
      if (st == null) {
        await _client.from("user_settings").insert({
          "user_id": pid,
          "api_key_encrypted": "",
          "secret_key_encrypted": "",
          "mode_otomatis": false,
          "koin_pilihan": <String>[],
          "margin_persen": 10,
          "leverage": 10,
        });
      } else {
        _mode = (st["mode_otomatis"] ?? false) as bool;
        final coins = (st["koin_pilihan"] as List?) ?? const [];
        _coins.text = coins.map((e) => e.toString()).join(", ");
        _lev.text = (st["leverage"] ?? 10).toString();
        _margin.text = (st["margin_persen"] ?? 10).toString();
        _tp.text = st["tp_persen"]?.toString() ?? "";
        _sl.text = st["sl_persen"]?.toString() ?? "";
        _tg.text = (st["tg_chat_id"] ?? "").toString();
      }
      if (mounted) {
        setState(() => _loaded = true);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _loaded = true;
          _msg = "Gagal memuat data: $e";
        });
      }
    }
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _msg = "Menyimpan...";
    });
    try {
      final pid = _profileId;
      if (pid == null) throw StateError("profil belum termuat");
      await _client
          .from("users_profile")
          .update({"nama": _nama.text.trim(), "no_hp": _hp.text.trim()})
          .eq("id", pid);
      final payload = <String, dynamic>{
        "user_id": pid,
        "mode_otomatis": _mode,
        "koin_pilihan": _coins.text.split(",").map((s) => s.trim()).where((s) => s.isNotEmpty).toList(),
        "leverage": _clampInt(_lev.text, 5, 10, 10),
        "margin_persen": _clampDouble(_margin.text, 1, 100, 10),
        "tp_persen": _tp.text.trim().isEmpty ? null : double.parse(_tp.text.trim()),
        "sl_persen": _sl.text.trim().isEmpty ? null : double.parse(_sl.text.trim()),
        "tg_chat_id": _tg.text.trim().isEmpty ? null : _tg.text.trim(),
        "updated_at": DateTime.now().toIso8601String(),
      };
      if (_api.text.trim().isNotEmpty) {
        payload["api_key_encrypted"] = _api.text.trim();
      }
      if (_sec.text.trim().isNotEmpty) {
        payload["secret_key_encrypted"] = _sec.text.trim();
      }
      await _client.from("user_settings").upsert(payload, onConflict: "user_id");
      _api.clear();
      _sec.clear();
      if (mounted) setState(() => _msg = "Tersimpan.");
    } catch (e) {
      if (mounted) setState(() => _msg = "Gagal simpan: $e");
    }
    if (mounted) setState(() => _busy = false);
  }

  int _clampInt(String raw, int lo, int hi, int dft) {
    final v = int.tryParse(raw.trim());
    if (v == null) return dft;
    return v.clamp(lo, hi);
  }

  double _clampDouble(String raw, double lo, double hi, double dft) {
    final v = double.tryParse(raw.trim());
    if (v == null) return dft;
    return v.clamp(lo, hi);
  }

  @override
  Widget build(BuildContext context) {
    if (!_loaded) {
      return const Center(child: CircularProgressIndicator(color: accentMain));
    }
    return ListView(
      padding: const EdgeInsets.only(top: 4, bottom: 30),
      children: [
        panelCard(
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 18),
          child: Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(colors: [accentMain, Color(0xFF0D9488)]),
                  boxShadow: [BoxShadow(color: Color(0x66000000), blurRadius: 12, offset: Offset(0, 6))],
                ),
                child: const Icon(Icons.rocket_launch, color: Color(0xFF032129)),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_email ?? "-", style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    const Text(
                      "Bot cron dijalankan tiap jam penuh (timeframe H1).",
                      style: TextStyle(color: textMuted, fontSize: 12.5),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        panelCard(
          child: SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text("Mode Otomatis", style: TextStyle(fontWeight: FontWeight.w700)),
            subtitle: Text(
              _mode
                  ? "Bot mengeksekusi order live (isolated margin, bracket SL/TP)."
                  : "Hanya sinyal dan riwayat simulasi (tanpa order live).",
              style: const TextStyle(color: textMuted, fontSize: 12.5),
            ),
            value: _mode,
            onChanged: (v) => setState(() => _mode = v),
          ),
        ),
        panelCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _SectionTitle("Profil"),
              const SizedBox(height: 12),
              TextField(controller: _nama, decoration: appDecoration(label: "Nama")),
              const SizedBox(height: 12),
              TextField(
                controller: _hp,
                keyboardType: TextInputType.phone,
                decoration: appDecoration(label: "No. HP"),
              ),
              const SizedBox(height: 16),
              const _SectionTitle("Strategi"),
              const SizedBox(height: 12),
              TextField(
                controller: _coins,
                decoration: appDecoration(
                  label: "Koin pilihan (pisah koma)",
                  hintText: "kosong = otomatis top-5 volume",
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _lev,
                      keyboardType: TextInputType.number,
                      decoration: appDecoration(label: "Leverage (5-10x)"),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _margin,
                      keyboardType: TextInputType.number,
                      decoration: appDecoration(label: "Margin (% saldo)"),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _tp,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: appDecoration(label: "TP % (kosong = ATR)"),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _sl,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: appDecoration(label: "SL % (kosong = ATR)"),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              const _SectionTitle("Kredensial & Notifikasi"),
              const SizedBox(height: 12),
              TextField(
                controller: _api,
                decoration: appDecoration(label: "BingX API Key", hintText: "kosongkan jika tidak diganti"),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _sec,
                obscureText: true,
                decoration: appDecoration(label: "BingX Secret Key", hintText: "kosongkan jika tidak diganti"),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _tg,
                decoration: appDecoration(label: "Telegram Chat ID", hintText: "opsional, notifikasi pribadi"),
              ),
              const SizedBox(height: 18),
              FilledButton(
                onPressed: _busy ? null : _save,
                child: _busy
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2.2, color: bgDeep),
                      )
                    : const Text("Simpan Pengaturan"),
              ),
              if (_msg != null) ...[
                const SizedBox(height: 12),
                Text(_msg!, style: const TextStyle(color: accentSoft, fontSize: 13, fontStyle: FontStyle.italic)),
              ],
              const SizedBox(height: 6),
              const Text(
                "API key plaintext otomatis dienkripsi engine pada run berikutnya.",
                style: TextStyle(color: textMuted, fontSize: 11.5),
              ),
            ],
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    for (final c in [_nama, _hp, _coins, _lev, _margin, _tp, _sl, _api, _sec, _tg]) {
      c.dispose();
    }
    super.dispose();
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: accentMain, letterSpacing: 1.6),
    );
  }
}
