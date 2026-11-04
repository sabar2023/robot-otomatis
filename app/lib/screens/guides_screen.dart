import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';

class GuidesScreen extends StatefulWidget {
  const GuidesScreen({super.key});

  @override
  State<GuidesScreen> createState() => _GuidesScreenState();
}

class _GuidesScreenState extends State<GuidesScreen> {
  bool _loading = true;
  String? _err;
  List<Map<String, dynamic>> _items = const [];
  int? _expanded;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final rows = await Supabase.instance.client.from("guides").select("*").order("created_at", ascending: false);
      if (!mounted) return;
      setState(() {
        _items = (rows as List).cast<Map<String, dynamic>>();
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Panduan")),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: accentMain))
          : _err != null
              ? Center(child: Text(_err!, style: const TextStyle(color: textMuted)))
              : ListView(
                  padding: const EdgeInsets.only(top: 4, bottom: 30),
                  children: _items.isEmpty
                      ? const [
                          SizedBox(height: 40),
                          Center(child: Text("Belum ada panduan.", style: TextStyle(color: textMuted))),
                        ]
                      : _items.asMap().entries.map((entry) {
                          final i = entry.key;
                          final v = entry.value;
                          final title = (v["title"] ?? "-").toString();
                          final body = (v["body"] ?? "").toString();
                          final open = _expanded == i;
                          return panelCard(
                            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                InkWell(
                                  onTap: () => setState(() => _expanded = open ? null : i),
                                  child: Row(
                                    children: [
                                      const Icon(Icons.article_outlined, color: accentMain),
                                      const SizedBox(width: 10),
                                      Expanded(child: Text(title, style: const TextStyle(fontWeight: FontWeight.w700))),
                                      Icon(open ? Icons.expand_less : Icons.expand_more, color: textMuted),
                                    ],
                                  ),
                                ),
                                if (open && body.isNotEmpty) ...[
                                  const SizedBox(height: 10),
                                  Text(body, style: const TextStyle(fontSize: 14, color: textMain, height: 1.5)),
                                ],
                              ],
                            ),
                          );
                        }).toList(),
                ),
    );
  }
}