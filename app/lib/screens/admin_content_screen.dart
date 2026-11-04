import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';

class AdminContentScreen extends StatefulWidget {
  const AdminContentScreen({super.key});

  @override
  State<AdminContentScreen> createState() => _AdminContentScreenState();
}

class _AdminContentScreenState extends State<AdminContentScreen> {
  bool _loading = true;
  String? _err;
  List<Map<String, dynamic>> _guides = const [];
  List<Map<String, dynamic>> _versions = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final client = Supabase.instance.client;
      final guides = await client.from("guides").select("*").order("created_at", ascending: false);
      final versions = await client.from("app_versions").select("*").order("created_at", ascending: false);
      if (!mounted) return;
      setState(() {
        _guides = (guides as List).cast<Map<String, dynamic>>();
        _versions = (versions as List).cast<Map<String, dynamic>>();
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

  Future<void> _addGuide() async {
    final titleCtrl = TextEditingController();
    final bodyCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: bgPanel,
        title: const Text("Tambah Panduan"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: titleCtrl, decoration: appDecoration(label: "Judul")),
            const SizedBox(height: 12),
            TextField(controller: bodyCtrl, maxLines: 4, decoration: appDecoration(label: "Isi")),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text("Batal")),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text("Simpan")),
        ],
      ),
    );
    if (ok != true) return;
    if (titleCtrl.text.trim().isEmpty) return;
    try {
      await Supabase.instance.client.from("guides").insert({"title": titleCtrl.text.trim(), "body": bodyCtrl.text.trim()});
      titleCtrl.dispose();
      bodyCtrl.dispose();
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
    }
  }

  Future<void> _addVersion() async {
    final platformCtrl = TextEditingController(text: "android");
    final versionCtrl = TextEditingController();
    final urlCtrl = TextEditingController();
    final notesCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: bgPanel,
        title: const Text("Tambah Versi Aplikasi"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: platformCtrl, decoration: appDecoration(label: "Platform (android/web)")),
            const SizedBox(height: 12),
            TextField(controller: versionCtrl, decoration: appDecoration(label: "Versi")),
            const SizedBox(height: 12),
            TextField(controller: urlCtrl, decoration: appDecoration(label: "Link Unduh")),
            const SizedBox(height: 12),
            TextField(controller: notesCtrl, maxLines: 2, decoration: appDecoration(label: "Catatan rilis")),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text("Batal")),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text("Simpan")),
        ],
      ),
    );
    if (ok != true) return;
    if (versionCtrl.text.trim().isEmpty) return;
    try {
      await Supabase.instance.client.from("app_versions").insert({
        "platform": platformCtrl.text.trim().isEmpty ? "android" : platformCtrl.text.trim(),
        "version": versionCtrl.text.trim(),
        "download_url": urlCtrl.text.trim().isEmpty ? null : urlCtrl.text.trim(),
        "release_notes": notesCtrl.text.trim().isEmpty ? null : notesCtrl.text.trim(),
        "is_active": true,
      });
      platformCtrl.dispose();
      versionCtrl.dispose();
      urlCtrl.dispose();
      notesCtrl.dispose();
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
    }
  }

  Future<void> _delete(String table, String id) async {
    try {
      await Supabase.instance.client.from(table).delete().eq("id", id);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Konten (Panduan & Versi)")),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: accentMain))
          : _err != null
              ? Center(child: Text(_err!, style: const TextStyle(color: textMuted)))
              : ListView(
                  padding: const EdgeInsets.only(top: 4, bottom: 30),
                  children: [
                    _sectionHeader("Panduan", _addGuide),
                    ..._guides.map((g) => _rowCard((g["title"] ?? "-").toString(), (g["body"] ?? "").toString(), () => _delete("guides", g["id"].toString()))),
                    const SizedBox(height: 16),
                    _sectionHeader("Versi Aplikasi", _addVersion),
                    ..._versions.map((v) => _rowCard(
                          "${v["version"]} (${v["platform"]})",
                          (v["release_notes"] ?? "").toString(),
                          () => _delete("app_versions", v["id"].toString()),
                        )),
                  ],
                ),
    );
  }

  Widget _sectionHeader(String label, VoidCallback onAdd) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 16, 4),
      child: Row(
        children: [
          Expanded(child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
          IconButton(onPressed: onAdd, icon: const Icon(Icons.add_circle, color: accentMain)),
        ],
      ),
    );
  }

  Widget _rowCard(String title, String subtitle, VoidCallback onDelete) {
    return panelCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                if (subtitle.isNotEmpty)
                  Text(subtitle, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: textMuted, fontSize: 12)),
              ],
            ),
          ),
          IconButton(onPressed: onDelete, icon: const Icon(Icons.delete_outline, color: dangerMain)),
        ],
      ),
    );
  }
}