import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';
import 'admin_content_screen.dart';
import 'admin_tickets_screen.dart';

class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key});

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  bool _loading = true;
  bool _isAdmin = false;
  String? _err;
  int _userCount = 0;
  int _paymentCount = 0;
  double _revenue = 0;
  List<Map<String, dynamic>> _users = const [];
  Map<String, TextEditingController> _setCtrls = {};
  Map<String, dynamic> _settings = {};

  final _settingKeys = [
    "trading_margin_mode",
    "trading_margin_pct",
    "trading_sl_pct",
    "trading_tp_pct",
    "trading_leverage",
    "feature_premium_active",
    "feature_free_active",
  ];

  @override
  void initState() {
    super.initState();
    for (final k in _settingKeys) {
      _setCtrls[k] = TextEditingController();
    }
    _load();
  }

  Future<void> _load() async {
    try {
      final client = Supabase.instance.client;
      final uid = client.auth.currentSession?.user.id;
      if (uid == null) return;
      final me = await client.from("users_profile").select("role").eq("auth_id", uid).maybeSingle();
      final admin = (me?["role"] ?? "customer") == "admin";
      _isAdmin = admin;
      if (!admin) {
        if (mounted) setState(() => _loading = false);
        return;
      }
      final users = await client.from("users_profile").select("*").order("created_at", ascending: false);
      final payments = await client.from("payments").select("*").eq("status", "paid");
      final settings = await client.from("admin_settings").select("*");
      double revenue = 0;
      for (final p in (payments as List)) {
        final amt = p["amount"];
        if (amt != null) revenue += double.tryParse(amt.toString()) ?? 0;
      }
      final settingsMap = <String, dynamic>{};
      for (final s in (settings as List)) {
        settingsMap[s["key"].toString()] = s["value"];
      }
      if (!mounted) return;
      setState(() {
        _users = (users as List).cast<Map<String, dynamic>>();
        _paymentCount = (payments as List).length;
        _revenue = revenue;
        _userCount = _users.length;
        _settings = settingsMap;
      });
      for (final k in _settingKeys) {
        _setCtrls[k]!.text = (settingsMap[k] ?? "").toString();
      }
      setState(() => _loading = false);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _err = "Gagal memuat: $e";
        _loading = false;
      });
    }
  }

  Future<void> _patchUser(String id, Map<String, dynamic> payload) async {
    try {
      await Supabase.instance.client.from("users_profile").update(payload).eq("id", id);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Tersimpan")));
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
      }
    }
  }

  Future<void> _loginAs(Map<String, dynamic> u) async {
    final token = Supabase.instance.client.auth.currentSession?.accessToken;
    final email = (u["email"] ?? "").toString();
    if (token == null || email.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Token/email tidak valid.")));
      return;
    }
    try {
      final resp = await http
          .post(
            Uri.parse("https://bot-cron.sabar2023.workers.dev/admin/login-as"),
            headers: {"Authorization": "Bearer $token", "Content-Type": "application/json"},
            body: jsonEncode({"email": email}),
          )
          .timeout(const Duration(seconds: 30));
      final body = jsonDecode(resp.body);
      if (resp.statusCode == 200 && body["url"] != null) {
        final url = body["url"].toString();
        await Clipboard.setData(ClipboardData(text: url));
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Link login $email tersalin. Buka di tab baru/incognito.")));
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: ${body["message"] ?? body["error"] ?? "HTTP ${resp.statusCode}"}")));
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
      }
    }
  }

  Future<void> _resetPassword(Map<String, dynamic> u) async {
    final email = (u["email"] ?? "-").toString();
    final ctrl = TextEditingController();
    final pwd = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: bgPanel,
        title: Text("Ubah Password $email"),
        content: TextField(
          controller: ctrl,
          obscureText: true,
          decoration: appDecoration(label: "Password Baru (min 6)"),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("Batal")),
          FilledButton(onPressed: () => Navigator.pop(ctx, ctrl.text.trim()), child: const Text("Simpan")),
        ],
      ),
    );
    ctrl.dispose();
    if (pwd == null || pwd.length < 6) {
      if (pwd != null) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Password minimal 6 karakter.")));
      }
      return;
    }
    final token = Supabase.instance.client.auth.currentSession?.accessToken;
    final authId = (u["auth_id"] ?? "").toString();
    if (token == null || authId.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("auth_id tidak ditemukan.")));
      return;
    }
    try {
      final resp = await http
          .post(
            Uri.parse("https://bot-cron.sabar2023.workers.dev/admin/set-password"),
            headers: {"Authorization": "Bearer $token", "Content-Type": "application/json"},
            body: jsonEncode({"auth_id": authId, "password": pwd}),
          )
          .timeout(const Duration(seconds: 30));
      if (resp.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Password $email berhasil diubah.")));
        }
      } else {
        if (mounted) {
          final body = jsonDecode(resp.body);
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: ${body["message"] ?? body["error"] ?? "HTTP ${resp.statusCode}"}")));
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
      }
    }
  }

  Future<void> _saveSettings() async {
    try {
      final rows = _settingKeys.map((k) => {"key": k, "value": _setCtrls[k]!.text.trim()}).toList();
      await Supabase.instance.client.from("admin_settings").upsert(rows);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Setelan sistem tersimpan")));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(appBar: AppBar(title: const Text("Dashboard Admin")), body: const Center(child: CircularProgressIndicator(color: accentMain)));
    }
    if (!_isAdmin) {
      return Scaffold(
        appBar: AppBar(title: const Text("Dashboard Admin")),
        body: const Center(child: Text("Akses ditolak.", style: TextStyle(color: textMuted))),
      );
    }
    if (_err != null) {
      return Scaffold(appBar: AppBar(title: const Text("Dashboard Admin")), body: Center(child: Text(_err!, style: const TextStyle(color: textMuted))));
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text("Dashboard Admin"),
        actions: [
          IconButton(
            icon: const Icon(Icons.support_agent, color: textMuted),
            tooltip: "Tiket",
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AdminTicketsScreen())),
          ),
          IconButton(
            icon: const Icon(Icons.article_outlined, color: textMuted),
            tooltip: "Konten",
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AdminContentScreen())),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.only(top: 4, bottom: 30),
        children: [
          panelCard(
            child: Row(
              children: [
                _statCard("User", "$_userCount"),
                const SizedBox(width: 10),
                _statCard("Pembayaran", "$_paymentCount"),
                const SizedBox(width: 10),
                _statCard("Pendapatan", "Rp${_revenue.toStringAsFixed(0)}"),
              ],
            ),
          ),
          const Padding(
            padding: EdgeInsets.fromLTRB(20, 8, 20, 4),
            child: Text("Manajemen Pengguna", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          ),
          ..._users.map(_buildUser),
          const SizedBox(height: 6),
          const Padding(
            padding: EdgeInsets.fromLTRB(20, 8, 20, 4),
            child: Text("Setelan Sistem Trading", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          ),
          panelCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _field("trading_margin_mode", "Margin mode (fixed/pct)"),
                const SizedBox(height: 10),
                _field("trading_margin_pct", "Margin % (saldo)"),
                const SizedBox(height: 10),
                _field("trading_sl_pct", "SL % default"),
                const SizedBox(height: 10),
                _field("trading_tp_pct", "TP % default"),
                const SizedBox(height: 10),
                _field("trading_leverage", "Leverage default"),
                const SizedBox(height: 10),
                _field("feature_premium_active", "Fitur Premium aktif (true/false)"),
                const SizedBox(height: 10),
                _field("feature_free_active", "Fitur Free aktif (true/false)"),
                const SizedBox(height: 14),
                FilledButton(onPressed: _saveSettings, child: const Text("Simpan Setelan")),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _statCard(String label, String value) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: bgPanelLight,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          children: [
            Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: accentSoft)),
            const SizedBox(height: 2),
            Text(label, style: const TextStyle(color: textMuted, fontSize: 11)),
          ],
        ),
      ),
    );
  }

  Widget _field(String key, String label) {
    return TextField(
      controller: _setCtrls[key],
      decoration: appDecoration(label: label),
    );
  }

  Widget _buildUser(Map<String, dynamic> u) {
    final id = u["id"].toString();
    final email = (u["email"] ?? "-").toString();
    final nama = (u["nama"] ?? email).toString();
    final plan = (u["plan"] ?? "free_trial").toString();
    final role = (u["role"] ?? "customer").toString();
    final kyc = (u["kyc_status"] ?? "pending").toString();
    final blocked = (u["is_blocked"] ?? false) == true;
    final premium = plan == "premium";
    return panelCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(nama, style: const TextStyle(fontWeight: FontWeight.w700)),
                    Text(email, style: const TextStyle(color: textMuted, fontSize: 12)),
                  ],
                ),
              ),
              _chip(plan, premium ? accentSoft : textMuted),
              const SizedBox(width: 6),
              _chip(role, role == "admin" ? upColor : accentMain),
            ],
          ),
          const SizedBox(height: 4),
          Text("KYC: $kyc | ${blocked ? "DIBLOKIR" : "aktif"}", style: TextStyle(color: blocked ? dangerMain : textMuted, fontSize: 12)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              _miniBtn(blocked ? "Buka Blokir" : "Blokir", () => _patchUser(id, {"is_blocked": !blocked})),
              _miniBtn(premium ? "Turunkan Free" : "Jadikan Premium", () => _patchUser(id, {"plan": premium ? "free_trial" : "premium"})),
              _miniBtn(kyc == "verified" ? "Batalkan KYC" : "Verifikasi KYC", () => _patchUser(id, {"kyc_status": kyc == "verified" ? "pending" : "verified"})),
              _miniBtn(role == "admin" ? "Jadikan Customer" : "Jadikan Admin", () => _patchUser(id, {"role": role == "admin" ? "customer" : "admin"})),
              _miniBtn("Login Pelanggan", () => _loginAs(u)),
              _miniBtn("Ubah Password", () => _resetPassword(u)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _chip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Text(text, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700)),
    );
  }

  Widget _miniBtn(String label, VoidCallback onTap) {
    return ActionChip(
      label: Text(label, style: const TextStyle(fontSize: 11)),
      onPressed: onTap,
      backgroundColor: bgPanelLight,
      side: const BorderSide(color: Color(0xFF155E6E)),
      labelStyle: const TextStyle(color: textMain, fontSize: 11),
    );
  }

  @override
  void dispose() {
    for (final c in _setCtrls.values) {
      c.dispose();
    }
    super.dispose();
  }
}