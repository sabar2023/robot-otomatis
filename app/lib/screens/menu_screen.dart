import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';
import 'account_screen.dart';
import 'admin_screen.dart';
import 'guides_screen.dart';
import 'tickets_screen.dart';
import 'update_screen.dart';

class MenuScreen extends StatefulWidget {
  const MenuScreen({super.key});

  @override
  State<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends State<MenuScreen> {
  bool _isAdmin = false;
  bool _loaded = false;

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
      final me = await client.from("users_profile").select("role").eq("auth_id", uid).maybeSingle();
      _isAdmin = (me?["role"] ?? "customer") == "admin";
    } catch (_) {}
    if (mounted) setState(() => _loaded = true);
  }

  void _push(BuildContext context, Widget screen) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => screen));
  }

  @override
  Widget build(BuildContext context) {
    if (!_loaded) {
      return const Center(child: CircularProgressIndicator(color: accentMain));
    }
    final items = <Widget>[
      if (_isAdmin)
        _item(Icons.admin_panel_settings_outlined, "Dashboard Admin", () => _push(context, const AdminScreen())),
      _item(Icons.person_outline, "Pengaturan Akun", () => _push(context, const AccountScreen())),
      _item(Icons.system_update_alt, "Update Aplikasi", () => _push(context, const UpdateScreen())),
      _item(Icons.support_agent, "Tiket Support", () => _push(context, const TicketsScreen())),
      _item(Icons.menu_book_outlined, "Panduan", () => _push(context, const GuidesScreen())),
    ];
    return ListView(
      padding: const EdgeInsets.only(top: 4, bottom: 30),
      children: items,
    );
  }

  Widget _item(IconData icon, String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: bgPanelLight,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: accentMain),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Text(label, style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w600)),
            ),
            const Icon(Icons.chevron_right, color: textMuted),
          ],
        ),
      ),
    );
  }
}