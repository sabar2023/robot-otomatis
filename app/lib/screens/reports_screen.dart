import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../profile.dart';
import '../theme.dart';
import 'package_screen.dart';

class ReportsScreen extends StatefulWidget {
  const ReportsScreen({super.key});

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  final _client = Supabase.instance.client;
  List<Map<String, dynamic>> _rows = [];
  bool _loaded = false;
  bool _locked = false;
  int _period = 2;

  static const _bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

  static const _periods = ["Harian", "Mingguan", "Bulanan", "Tahunan"];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final access = await fetchSignalAccess();
      if (!mounted) return;
      _locked = access != "premium";
      if (_locked) {
        setState(() => _loaded = true);
        return;
      }
      final pid = await ensureProfile();
      if (pid == null || !mounted) return;
      final rows = await _client
          .from("trade_history")
          .select("symbol,direction,entry_price,sl_price,tp_price,pnl,closed_at,executed_at,margin_used")
          .eq("user_id", pid)
          .eq("status", "closed")
          .order("closed_at", ascending: false)
          .limit(500);
      if (!mounted) return;
      setState(() {
        _rows = List<Map<String, dynamic>>.from(rows);
        _loaded = true;
      });
    } catch (_) {
      if (mounted) setState(() => _loaded = true);
    }
  }

  double? _pnl(dynamic v) {
    if (v == null) return null;
    try {
      return (v as num).toDouble();
    } catch (_) {
      return null;
    }
  }

  DateTime? _date(Map<String, dynamic> r) {
    for (final k in const ["closed_at", "executed_at"]) {
      final raw = r[k];
      if (raw == null) continue;
      try {
        return DateTime.parse(raw.toString()).toLocal();
      } catch (_) {}
    }
    return null;
  }

  String _two(int v) => v.toString().padLeft(2, "0");

  String _money(double v) => (v >= 0 ? "+" : "") + v.toStringAsFixed(2);

  String _label(DateTime d) {
    switch (_period) {
      case 0:
        return "${_two(d.day)} ${_bulan[d.month - 1]} ${d.year}";
      case 1:
        final start = d.subtract(Duration(days: d.weekday - 1));
        final end = start.add(const Duration(days: 6));
        return "${_two(start.day)} ${_bulan[start.month - 1]} - ${_two(end.day)} ${_bulan[end.month - 1]} ${end.year}";
      case 2:
        return "${_bulan[d.month - 1]} ${d.year}";
      default:
        return "${d.year}";
    }
  }

  String _key(DateTime d) {
    switch (_period) {
      case 0:
        return "${d.year}-${_two(d.month)}-${_two(d.day)}";
      case 1:
        final start = d.subtract(Duration(days: d.weekday - 1));
        return "${start.year}-${_two(start.month)}-${_two(start.day)}";
      case 2:
        return "${d.year}-${_two(d.month)}";
      default:
        return "${d.year}";
    }
  }

  List<Map<String, dynamic>> _grouped() {
    final buckets = <String, List<double>>{};
    final firstDate = <String, DateTime>{};
    for (final r in _rows) {
      final p = _pnl(r["pnl"]);
      if (p == null) continue;
      final d = _date(r);
      if (d == null) continue;
      final k = _key(d);
      final b = buckets.putIfAbsent(k, () => [0, 0, 0, 0, 0]);
      b[0]++;
      b[1] += p;
      if (p > 0) {
        b[2]++;
        b[4] += p;
      } else {
        b[3]++;
      }
      firstDate[k] = d;
    }
    final keys = buckets.keys.toList()..sort((a, b) => b.compareTo(a));
    return keys.map((k) {
      final b = buckets[k]!;
      return {
        "key": k,
        "label": _label(firstDate[k]!),
        "n": b[0].toInt(),
        "pnl": b[1],
        "wins": b[2].toInt(),
        "losses": b[3].toInt(),
        "gross": b[4],
      };
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    if (!_loaded) {
      return const Center(child: CircularProgressIndicator(color: accentMain));
    }
    if (_locked) {
      return _buildLock();
    }
    final groups = _grouped();
    final totalPnl = groups.fold<double>(0, (s, g) => s + (g["pnl"] as double));
    final totalN = groups.fold<int>(0, (s, g) => s + (g["n"] as int));
    final totalW = groups.fold<int>(0, (s, g) => s + (g["wins"] as int));
    final winrate = totalN > 0 ? totalW / totalN * 100.0 : 0.0;
    return RefreshIndicator(
      onRefresh: _load,
      color: accentMain,
      child: ListView(
        padding: const EdgeInsets.only(top: 4, bottom: 30),
        children: [
          panelCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text("Laporan Keuntungan", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                const SizedBox(height: 12),
                SegmentedButton<int>(
                  segments: [
                    for (var i = 0; i < _periods.length; i++)
                      ButtonSegment(value: i, label: Text(_periods[i])),
                  ],
                  selected: <int>{_period},
                  onSelectionChanged: (s) => setState(() => _period = s.first),
                ),
                const SizedBox(height: 16),
                _summary("Total PnL", _money(totalPnl), color: totalPnl >= 0 ? upColor : downColor),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(child: _summary("Trade", totalN.toString())),
                    Expanded(child: _summary("Win", totalW.toString())),
                    Expanded(child: _summary("Loss", (totalN - totalW).toString())),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(child: _summary("Winrate", "${winrate.toStringAsFixed(1)}%")),
                    Expanded(child: _summary("Rata-rata", _money(totalN > 0 ? totalPnl / totalN : 0))),
                  ],
                ),
              ],
            ),
          ),
          if (groups.isEmpty)
            panelCard(
              child: const Center(
                child: Text("Belum ada trade tertutup dengan PnL.", style: TextStyle(color: textMuted)),
              ),
            ),
          for (final g in groups) _periodCard(g),
        ],
      ),
    );
  }

  Widget _buildLock() {
    return ListView(
      padding: const EdgeInsets.only(top: 40),
      children: [
        panelCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(Icons.lock_outline, color: accentMain, size: 44),
              const SizedBox(height: 14),
              const Text(
                "Laporan adalah fitur Premium",
                textAlign: TextAlign.center,
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
              ),
              const SizedBox(height: 6),
              const Text(
                "Upgrade ke Premium untuk melihat laporan keuntungan, winrate, dan riwayat PnL.",
                textAlign: TextAlign.center,
                style: TextStyle(color: textMuted, fontSize: 13),
              ),
              const SizedBox(height: 18),
              FilledButton(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PackageScreen())),
                child: const Text("Upgrade ke Premium"),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _summary(String label, String value, {Color? color}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label.toUpperCase(), style: const TextStyle(color: textMuted, fontSize: 10, letterSpacing: 0.8)),
        const SizedBox(height: 3),
        Text(value, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: color ?? textMain)),
      ],
    );
  }

  Widget _periodCard(Map<String, dynamic> g) {
    final n = g["n"] as int;
    final pnl = g["pnl"] as double;
    final wins = g["wins"] as int;
    final winrate = n > 0 ? wins / n * 100.0 : 0.0;
    return panelCard(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(g["label"].toString(), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14)),
                const SizedBox(height: 4),
                Text(
                  "$n trade | Win $wins | Winrate ${winrate.toStringAsFixed(1)}%",
                  style: const TextStyle(color: textMuted, fontSize: 12),
                ),
              ],
            ),
          ),
          Text(
            _money(pnl),
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: pnl >= 0 ? upColor : downColor),
          ),
        ],
      ),
    );
  }
}