import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';
import 'ticket_chat_screen.dart';

class AdminTicketsScreen extends StatefulWidget {
  const AdminTicketsScreen({super.key});

  @override
  State<AdminTicketsScreen> createState() => _AdminTicketsScreenState();
}

class _AdminTicketsScreenState extends State<AdminTicketsScreen> {
  bool _loading = true;
  String? _err;
  List<Map<String, dynamic>> _tickets = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final rows = await Supabase.instance.client
          .from("support_tickets")
          .select("*,users_profile(email,nama)")
          .order("created_at", ascending: false);
      if (!mounted) return;
      setState(() {
        _tickets = (rows as List).cast<Map<String, dynamic>>();
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _err = "Gagal memuat: $e";
        _loading = false;
      });
    }
  }

  Future<void> _setStatus(String id, String status) async {
    try {
      await Supabase.instance.client.from("support_tickets").update({"status": status}).eq("id", id);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
    }
  }

  Future<void> _delete(String id) async {
    try {
      await Supabase.instance.client.from("support_tickets").delete().eq("id", id);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
    }
  }

  Future<void> _confirmDelete(String id) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: bgPanel,
        title: const Text("Hapus tiket?"),
        content: const Text("Tiket dan semua pesannya akan dihapus."),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text("Batal")),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text("Hapus")),
        ],
      ),
    );
    if (ok == true) await _delete(id);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Semua Tiket")),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: accentMain))
          : _err != null
              ? Center(child: Text(_err!, style: const TextStyle(color: textMuted)))
              : ListView(
                  padding: const EdgeInsets.only(top: 4, bottom: 30),
                  children: _tickets.isEmpty
                      ? const [
                          SizedBox(height: 80),
                          Center(child: Text("Belum ada tiket.", style: TextStyle(color: textMuted))),
                        ]
                      : _tickets.map(_buildTicket).toList(),
                ),
    );
  }

  Widget _buildTicket(Map<String, dynamic> t) {
    final id = t["id"].toString();
    final subject = (t["subject"] ?? "-").toString();
    final status = (t["status"] ?? "open").toString();
    final prof = t["users_profile"];
    final nama = prof is Map ? ((prof["nama"] ?? "-").toString()) : "-";
    final email = prof is Map ? ((prof["email"] ?? "-").toString()) : "-";
    return InkWell(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => TicketChatScreen(ticketId: id, subject: subject, isAdmin: true)),
      ),
      child: panelCard(
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
                      Text(subject, style: const TextStyle(fontWeight: FontWeight.w700)),
                      Text("$nama · $email", style: const TextStyle(color: textMuted, fontSize: 12)),
                    ],
                  ),
                ),
                _chip(status),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              children: [
                ActionChip(
                  label: const Text("Buka", style: TextStyle(fontSize: 11, color: textMain)),
                  onPressed: () => _setStatus(id, "open"),
                  backgroundColor: bgPanelLight,
                  side: const BorderSide(color: Color(0xFF155E6E)),
                ),
                ActionChip(
                  label: const Text("Tutup", style: TextStyle(fontSize: 11, color: textMain)),
                  onPressed: () => _setStatus(id, "closed"),
                  backgroundColor: bgPanelLight,
                  side: const BorderSide(color: Color(0xFF155E6E)),
                ),
                ActionChip(
                  label: const Text("Hapus", style: TextStyle(fontSize: 11, color: dangerMain)),
                  onPressed: () => _confirmDelete(id),
                  backgroundColor: bgPanelLight,
                  side: const BorderSide(color: dangerMain),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String status) {
    final color = status == "closed" ? textMuted : (status == "open" ? accentSoft : accentMain);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(20), border: Border.all(color: color.withOpacity(0.5))),
      child: Text(status, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
    );
  }
}