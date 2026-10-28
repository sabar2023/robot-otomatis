import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../profile.dart';
import '../theme.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final _client = Supabase.instance.client;
  List<Map<String, dynamic>> _rows = [];
  bool _loaded = false;

  static const _bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

  @override
  void initState() {
    super.initState();
    _load();
  }

  String _two(int v) => v.toString().padLeft(2, "0");

  String _fmt(String? raw) {
    if (raw == null || raw.isEmpty) return "-";
    try {
      final dt = DateTime.parse(raw).toLocal();
      return "${_two(dt.day)} ${_bulan[dt.month - 1]} ${dt.year} ${_two(dt.hour)}:${_two(dt.minute)}";
    } catch (_) {
      return raw;
    }
  }

  String _num(dynamic v) {
    if (v == null) return "-";
    try {
      final d = (v as num).toDouble();
      return d.toStringAsFixed(d.abs() < 1 ? 4 : 2);
    } catch (_) {
      return v.toString();
    }
  }

  String _pnlStr(dynamic v) {
    if (v == null) return "—";
    try {
      final d = (v as num).toDouble();
      return (d >= 0 ? "+" : "") + d.toStringAsFixed(2);
    } catch (_) {
      return v.toString();
    }
  }

  Color _pnlColor(dynamic v) {
    if (v == null) return textMuted;
    final d = (v as num).toDouble();
    return d >= 0 ? upColor : downColor;
  }

  Future<void> _load() async {
    try {
      final pid = await ensureProfile();
      if (pid == null || !mounted) return;
      final rows = await _client
          .from("trade_history")
          .select("*")
          .eq("user_id", pid)
          .order("executed_at", ascending: false)
          .limit(100);
      if (!mounted) return;
      setState(() {
        _rows = List<Map<String, dynamic>>.from(rows);
        _loaded = true;
      });
    } catch (_) {
      if (mounted) setState(() => _loaded = true);
    }
  }

  Future<void> _del(Map<String, dynamic> t) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text("Hapus riwayat?"),
        content: Text("${t["symbol"]} (${t["direction"]}) akan dihapus permanen."),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text("Batal")),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text("Hapus")),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _client.from("trade_history").delete().eq("id", t["id"]);
      _load();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (!_loaded) {
      return const Center(child: CircularProgressIndicator(color: accentMain));
    }
    return RefreshIndicator(
      onRefresh: _load,
      color: accentMain,
      child: _rows.isEmpty
          ? ListView(
              children: [
                const SizedBox(height: 130),
                panelCard(
                  child: const Center(
                    child: Text(
                      "Belum ada data trade untuk akun ini.",
                      style: TextStyle(color: textMuted),
                    ),
                  ),
                ),
              ],
            )
          : ListView.builder(
              padding: const EdgeInsets.only(bottom: 30),
              itemCount: _rows.length,
              itemBuilder: (c, i) => _buildCard(_rows[i]),
            ),
    );
  }

  Widget _buildCard(Map<String, dynamic> t) {
    final long = (t["direction"] ?? "").toString().toUpperCase() == "LONG";
    final status = (t["status"] ?? "").toString();
    final open = status == "open";
    return panelCard(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(t["symbol"].toString(), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: long ? const Color(0x334ADE80) : const Color(0x33F87171),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  t["direction"].toString(),
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: long ? upColor : downColor),
                ),
              ),
              const Spacer(),
              Text(_fmt(t["executed_at"]?.toString()), style: const TextStyle(color: textMuted, fontSize: 11.5)),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _tile("Entry", _num(t["entry_price"]))),
              Expanded(child: _tile("SL", _num(t["sl_price"]))),
              Expanded(child: _tile("TP", _num(t["tp_price"]))),
              Expanded(child: _tile("Leverage", "${t["leverage"]}x")),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(child: _tile("PnL", _pnlStr(t["pnl"]), color: _pnlColor(t["pnl"]))),
              Expanded(
                child: _tile(
                  "Status",
                  open ? "OPEN" : status,
                  color: open ? upColor : textMuted,
                ),
              ),
              const SizedBox(width: 8),
              TextButton.icon(
                onPressed: () => _del(t),
                icon: const Icon(Icons.delete_outline, size: 17, color: dangerMain),
                label: const Text("Hapus", style: TextStyle(color: dangerMain, fontSize: 13)),
                style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 8)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _tile(String label, String value, {Color? color}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label.toUpperCase(), style: const TextStyle(color: textMuted, fontSize: 10, letterSpacing: 0.8)),
        const SizedBox(height: 3),
        Text(value, style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: color ?? textMain)),
      ],
    );
  }
}
