import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';

class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key});

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  final _nama = TextEditingController();
  final _akun = TextEditingController();
  final _hp = TextEditingController();
  final _pass = TextEditingController();

  String? _pid;
  String _email = "";
  String _kycStatus = "pending";
  String? _ktpUrl;
  String? _selfieUrl;
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
      final prof = await client.from("users_profile").select("*").eq("auth_id", uid).maybeSingle();
      if (prof == null) return;
      _pid = prof["id"]?.toString();
      _email = (prof["email"] ?? "").toString();
      _kycStatus = (prof["kyc_status"] ?? "pending").toString();
      _ktpUrl = (prof["ktp_image_url"] ?? "").toString();
      _selfieUrl = (prof["selfie_image_url"] ?? "").toString();
      _nama.text = (prof["nama"] ?? "").toString();
      _akun.text = (prof["nama_akun"] ?? "").toString();
      _hp.text = (prof["no_hp"] ?? "").toString();
      if (mounted) setState(() => _loaded = true);
    } catch (e) {
      if (mounted) setState(() {
        _loaded = true;
        _msg = "Gagal memuat: $e";
      });
    }
  }

  Future<String?> _upload(ImageSource source, String kind) async {
    final picker = ImagePicker();
    final x = await picker.pickImage(source: source, maxWidth: 1200, imageQuality: 80);
    if (x == null) return null;
    final bytes = await x.readAsBytes();
    final name = x.name.isEmpty ? "$kind.jpg" : x.name;
    final ext = name.contains(".") ? name.split(".").last : "jpg";
    final path = "${_pid ?? 'user'}/${DateTime.now().millisecondsSinceEpoch}_$kind.$ext";
    await Supabase.instance.client.storage.from("kyc").uploadBinary(path, bytes);
    return Supabase.instance.client.storage.from("kyc").getPublicUrl(path);
  }

  Future<void> _pickKtp() async {
    final url = await _upload(ImageSource.gallery, "ktp");
    if (url != null) {
      _ktpUrl = url;
      setState(() {});
    }
  }

  Future<void> _pickSelfie() async {
    final url = await _upload(ImageSource.gallery, "selfie");
    if (url != null) {
      _selfieUrl = url;
      setState(() {});
    }
  }

  bool get _complete =>
      _nama.text.trim().isNotEmpty &&
      _akun.text.trim().isNotEmpty &&
      _hp.text.trim().isNotEmpty &&
      (_ktpUrl?.isNotEmpty ?? false) &&
      (_selfieUrl?.isNotEmpty ?? false);

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _msg = "Menyimpan...";
    });
    try {
      final pid = _pid;
      if (pid == null) throw StateError("profil belum termuat");
      await Supabase.instance.client.from("users_profile").update({
        "nama": _nama.text.trim(),
        "nama_akun": _akun.text.trim(),
        "no_hp": _hp.text.trim(),
        "ktp_image_url": _ktpUrl,
        "selfie_image_url": _selfieUrl,
        "kyc_status": _complete ? "verified" : "pending",
      }).eq("id", pid);
      setState(() {
        _kycStatus = _complete ? "verified" : "pending";
        _msg = "Tersimpan.";
      });
    } catch (e) {
      setState(() => _msg = "Gagal simpan: $e");
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _changePassword() async {
    final p = _pass.text.trim();
    if (p.length < 6) {
      setState(() => _msg = "Kata sandi minimal 6 karakter.");
      return;
    }
    setState(() {
      _busy = true;
      _msg = "Mengubah kata sandi...";
    });
    try {
      await Supabase.instance.client.auth.updateUser(UserAttributes(password: p));
      _pass.clear();
      setState(() => _msg = "Kata sandi berhasil diubah.");
    } catch (e) {
      setState(() => _msg = "Gagal ubah sandi: $e");
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_loaded) {
      return Scaffold(appBar: AppBar(title: const Text("Pengaturan Akun")), body: const Center(child: CircularProgressIndicator(color: accentMain)));
    }
    return Scaffold(
      appBar: AppBar(title: const Text("Pengaturan Akun")),
      body: ListView(
        padding: const EdgeInsets.only(top: 4, bottom: 30),
        children: [
          panelCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Icon(Icons.badge_outlined, color: accentMain),
                    const SizedBox(width: 10),
                    const Text("Profil & KYC", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                    const Spacer(),
                    _kycChip(),
                  ],
                ),
                const SizedBox(height: 14),
                TextField(controller: _nama, decoration: appDecoration(label: "Nama Lengkap")),
                const SizedBox(height: 12),
                TextField(controller: _akun, decoration: appDecoration(label: "Nama Akun")),
                const SizedBox(height: 12),
                TextField(controller: _hp, keyboardType: TextInputType.phone, decoration: appDecoration(label: "No HP")),
                const SizedBox(height: 6),
                Text("Email: $_email", style: const TextStyle(color: textMuted, fontSize: 12.5)),
                const SizedBox(height: 12),
                _uploadTile("Foto KTP", _ktpUrl, _pickKtp),
                const SizedBox(height: 10),
                _uploadTile("Foto Selfie dengan KTP", _selfieUrl, _pickSelfie),
              ],
            ),
          ),
          panelCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text("Ubah Kata Sandi", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                const SizedBox(height: 12),
                TextField(controller: _pass, obscureText: true, decoration: appDecoration(label: "Kata Sandi Baru")),
              ],
            ),
          ),
          if (_msg != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 0),
              child: Text(_msg!, style: const TextStyle(color: accentSoft, fontSize: 13)),
            ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: FilledButton(onPressed: _busy ? null : _save, child: const Text("Simpan Profil")),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: OutlinedButton(onPressed: _busy ? null : _changePassword, child: const Text("Ubah Kata Sandi")),
          ),
        ],
      ),
    );
  }

  Widget _kycChip() {
    final verified = _kycStatus == "verified";
    final color = verified ? upColor : accentSoft;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Text(verified ? "TERVERIFIKASI" : "PENDING", style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w700)),
    );
  }

  Widget _uploadTile(String label, String? url, VoidCallback onTap) {
    final has = url != null && url.isNotEmpty;
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF062830),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: has ? upColor : const Color(0xFF155E6E)),
        ),
        child: Row(
          children: [
            Icon(has ? Icons.check_circle : Icons.upload_file, color: has ? upColor : textMuted),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                has ? "$label (terunggah)" : label,
                style: TextStyle(color: has ? upColor : textMain, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _nama.dispose();
    _akun.dispose();
    _hp.dispose();
    _pass.dispose();
    super.dispose();
  }
}