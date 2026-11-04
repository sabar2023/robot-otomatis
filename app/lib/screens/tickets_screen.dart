import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';
import 'ticket_chat_screen.dart';

class TicketsScreen extends StatefulWidget {
  const TicketsScreen({super.key});

  @override
  State<TicketsScreen> createState() => _TicketsScreenState();
}

class _TicketsScreenState extends State<TicketsScreen> {
  String? _pid;
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
      final client = Supabase.instance.client;
      final uid = client.auth.currentSession?.user.id;
      if (uid == null) return;
      final prof = await client.from("users_profile").select("id").eq("auth_id", uid).maybeSingle();
      final pid = prof?["id"]?.toString();
      _pid = pid;
      if (pid == null) return;
      final rows = await client
          .from("support_tickets")
          .select("*")
          .eq("user_id", pid)
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

  Future<void> _create() async {
    final subjectCtrl = TextEditingController();
    final msgCtrl = TextEditingController();
    final title = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: bgPanel,
        title: const Text("Tiket Baru"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: subjectCtrl,
              decoration: appDecoration(label: "Subjek"),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: msgCtrl,
              maxLines: 3,
              decoration: appDecoration(label: "Pesan"),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("Batal")),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, subjectCtrl.text.trim()),
            child: const Text("Kirim"),
          ),
        ],
      ),
    );
    if (title == null || title.isEmpty) return;
    try {
      final client = Supabase.instance.client;
      final ticket = await client
          .from("support_tickets")
          .insert({"user_id": _pid, "subject": title, "status": "open"})
          .select()
          .single();
      final tid = ticket["id"].toString();
      if (msgCtrl.text.trim().isNotEmpty) {
        await client.from("ticket_messages").insert({
          "ticket_id": tid,
          "sender": "user",
          "message": msgCtrl.text.trim(),
        });
      }
      subjectCtrl.dispose();
      msgCtrl.dispose();
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Tiket Support")),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _create,
        backgroundColor: accentMain,
        foregroundColor: bgDeep,
        icon: const Icon(Icons.add),
        label: const Text("Buat Tiket"),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: accentMain))
          : _err != null
              ? Center(child: Text(_err!, style: const TextStyle(color: textMuted)))
              : ListView(
                  padding: const EdgeInsets.only(top: 4, bottom: 90),
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
    final subject = (t["subject"] ?? "-").toString();
    final status = (t["status"] ?? "open").toString();
    final created = DateTime.tryParse((t["created_at"] ?? "").toString());
    final tid = t["id"].toString();
    return InkWell(
      onTap: () {
        Navigator.of(context).push(MaterialPageRoute(builder: (_) => TicketChatScreen(ticketId: tid, subject: subject)));
      },
      child: panelCard(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        child: Row(
          children: [
            const Icon(Icons.chat_bubble_outline, color: accentMain),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(subject, style: const TextStyle(fontWeight: FontWeight.w700)),
                  if (created != null)
                    Text(
                      "${created.day.toString().padLeft(2, '0')}-${created.month.toString().padLeft(2, '0')}-${created.year}",
                      style: const TextStyle(color: textMuted, fontSize: 12),
                    ),
                ],
              ),
            ),
            _statusChip(status),
          ],
        ),
      ),
    );
  }

  Widget _statusChip(String status) {
    final color = status == "closed" ? textMuted : (status == "open" ? accentSoft : accentMain);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Text(status, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
    );
  }
}