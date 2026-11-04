import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';

class TicketChatScreen extends StatefulWidget {
  const TicketChatScreen({super.key, required this.ticketId, required this.subject});

  final String ticketId;
  final String subject;

  @override
  State<TicketChatScreen> createState() => _TicketChatScreenState();
}

class _TicketChatScreenState extends State<TicketChatScreen> {
  final _msg = TextEditingController();
  bool _sending = false;
  List<Map<String, dynamic>> _messages = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final rows = await Supabase.instance.client
          .from("ticket_messages")
          .select("*")
          .eq("ticket_id", widget.ticketId)
          .order("created_at", ascending: true);
      if (!mounted) return;
      setState(() {
        _messages = (rows as List).cast<Map<String, dynamic>>();
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal memuat: $e")));
      }
    }
  }

  Future<void> _send() async {
    final text = _msg.text.trim();
    if (text.isEmpty) return;
    setState(() => _sending = true);
    try {
      await Supabase.instance.client.from("ticket_messages").insert({
        "ticket_id": widget.ticketId,
        "sender": "user",
        "message": text,
      });
      _msg.clear();
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.subject)),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length,
              itemBuilder: (ctx, i) {
                final m = _messages[i];
                final mine = (m["sender"] ?? "user") == "user";
                final text = (m["message"] ?? "").toString();
                return Align(
                  alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: mine ? accentMain : bgPanelLight,
                      borderRadius: BorderRadius.circular(16).copyWith(
                        bottomRight: mine ? const Radius.circular(2) : null,
                        bottomLeft: mine ? null : const Radius.circular(2),
                      ),
                    ),
                    child: Text(
                      text,
                      style: TextStyle(color: mine ? bgDeep : textMain, fontSize: 14.5),
                    ),
                  ),
                );
              },
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _msg,
                      decoration: appDecoration(label: "Tulis pesan..."),
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 10),
                  IconButton.filled(
                    onPressed: _sending ? null : _send,
                    icon: const Icon(Icons.send),
                    style: IconButton.styleFrom(backgroundColor: accentMain, foregroundColor: bgDeep),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _msg.dispose();
    super.dispose();
  }
}