import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';

class PackageScreen extends StatefulWidget {
  const PackageScreen({super.key});

  @override
  State<PackageScreen> createState() => _PackageScreenState();
}

class _PackageScreenState extends State<PackageScreen> {
  String _plan = "free_trial";
  String? _trialEndsAt;
  String _kycStatus = "pending";
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
      final client = Supabase.instance.client;
      final uid = client.auth.currentSession?.user.id;
      if (uid == null) return;
      final prof = await client.from("users_profile").select("plan,trial_ends_at,kyc_status").eq("auth_id", uid).maybeSingle();
      if (prof != null) {
        _plan = (prof["plan"] ?? "free_trial").toString();
        _trialEndsAt = (prof["trial_ends_at"] ?? "").toString();
        _kycStatus = (prof["kyc_status"] ?? "pending").toString();
      }
      if (mounted) setState(() => _loaded = true);
    } catch (e) {
      if (mounted) setState(() {
        _loaded = true;
        _msg = "Gagal memuat: $e";
      });
    }
  }

  int _trialDaysLeft() {
    if (_trialEndsAt == null || _trialEndsAt!.isEmpty) return 0;
    final end = DateTime.tryParse(_trialEndsAt!);
    if (end == null) return 0;
    final diff = end.difference(DateTime.now());
    return diff.inDays + 1;
  }

  Future<void> _confirmUpgrade() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: bgPanel,
        title: const Text("Upgrade ke Premium"),
        content: const Text(
          "Rp500.000/bulan\n\nFitur Premium:\n- Live order otomatis\n- Mode manual (leverage/TP/SL sendiri)\n- Margin dinamis (compounding)\n- Laporan lengkap\n\nPembayaran melalui Duitku. Setelah dibayar, paket aktif otomatis.",
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text("Batal")),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text("Lanjut Bayar")),
        ],
      ),
    );
    if (ok != true) return;
    final token = Supabase.instance.client.auth.currentSession?.accessToken;
    if (token == null) {
      setState(() => _msg = "Belum login.");
      return;
    }
    setState(() {
      _busy = true;
      _msg = "Membuat pembayaran...";
    });
    try {
      final resp = await http.post(
        Uri.parse("https://bot-cron.sabar2023.workers.dev/pay"),
        headers: {"Authorization": "Bearer $token", "Content-Type": "application/json"},
      ).timeout(const Duration(seconds: 30));
      final body = jsonDecode(resp.body);
      if (resp.statusCode == 200 && body["paymentUrl"] != null) {
        final url = body["paymentUrl"].toString();
        setState(() => _msg = "Buka link pembayaran (tersalin):\n$url");
        await Clipboard.setData(ClipboardData(text: url));
      } else {
        setState(() => _msg = "Gagal: ${body["message"] ?? body["error"] ?? "HTTP ${resp.statusCode}"}");
      }
    } catch (e) {
      setState(() => _msg = "Gagal memicu pembayaran: $e");
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_loaded) {
      return const Center(child: CircularProgressIndicator(color: accentMain));
    }
    final premium = _plan == "premium";
    final daysLeft = _trialDaysLeft();
    return ListView(
      padding: const EdgeInsets.only(top: 4, bottom: 30),
      children: [
        panelCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Icon(premium ? Icons.workspace_premium : Icons.hourglass_empty, color: accentMain),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      premium ? "Paket Premium" : "Paket Trial Gratis",
                      style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              if (!premium && daysLeft > 0)
                Text("Sisa trial: $daysLeft hari", style: const TextStyle(color: accentSoft, fontWeight: FontWeight.w600)),
              if (!premium && daysLeft <= 0)
                const Text("Trial berakhir.", style: TextStyle(color: dangerMain, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Text(
                premium ? "Live order + sinyal + mode manual + margin dinamis + laporan." : "Hanya sinyal (simulasi). Live order memerlukan Premium.",
                style: const TextStyle(color: textMuted, fontSize: 13),
              ),
              const SizedBox(height: 6),
              Text(
                "Status KYC: ${_kycStatus == "verified" ? "Terverifikasi" : "Pending"}",
                style: const TextStyle(color: textMuted, fontSize: 12.5),
              ),
            ],
          ),
        ),
        if (!premium) ...[
          panelCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text("Premium", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                const SizedBox(height: 4),
                const Text("Rp500.000 / bulan", style: TextStyle(color: accentSoft, fontSize: 22, fontWeight: FontWeight.w800)),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: _busy ? null : _confirmUpgrade,
                  child: Text(_busy ? "Memproses..." : "Upgrade Sekarang"),
                ),
              ],
            ),
          ),
        ],
        if (_msg != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
            child: Text(_msg!, style: const TextStyle(color: accentSoft, fontSize: 13)),
          ),
      ],
    );
  }
}