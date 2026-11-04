import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';

class UpdateScreen extends StatefulWidget {
  const UpdateScreen({super.key});

  @override
  State<UpdateScreen> createState() => _UpdateScreenState();
}

class _UpdateScreenState extends State<UpdateScreen> {
  bool _loading = true;
  String? _err;
  List<Map<String, dynamic>> _items = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final rows = await Supabase.instance.client
          .from("app_versions")
          .select("*")
          .eq("is_active", true)
          .order("created_at", ascending: false);
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

  void _copy(String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Link disalin")));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Update Aplikasi")),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: accentMain))
          : _err != null
              ? Center(child: Text(_err!, style: const TextStyle(color: textMuted)))
              : ListView(
                  padding: const EdgeInsets.only(top: 4, bottom: 30),
                  children: _items.isEmpty
                      ? const [
                          SizedBox(height: 40),
                          Center(child: Text("Belum ada rilis.", style: TextStyle(color: textMuted))),
                        ]
                      : _items.map(_buildCard).toList(),
                ),
    );
  }

  Widget _buildCard(Map<String, dynamic> v) {
    final version = (v["version"] ?? "-").toString();
    final platform = (v["platform"] ?? "-").toString();
    final notes = (v["release_notes"] ?? "").toString();
    final url = (v["download_url"] ?? "").toString();
    return panelCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.system_update_alt, color: accentMain),
              const SizedBox(width: 10),
              Expanded(
                child: Text("Versi $version", style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
              ),
              Text(platform, style: const TextStyle(color: textMuted, fontSize: 12)),
            ],
          ),
          if (notes.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(notes, style: const TextStyle(fontSize: 13, color: textMuted)),
          ],
          if (url.isNotEmpty) ...[
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () => _copy(url),
              icon: const Icon(Icons.link),
              label: const Text("Salin Link Unduh"),
            ),
          ],
        ],
      ),
    );
  }
}