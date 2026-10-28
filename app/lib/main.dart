import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'screens/auth_screen.dart';
import 'screens/main_shell.dart';
import 'theme.dart';

const supabaseUrl = "https://jklbczruvbxscpwxxfud.supabase.co";
const supabaseAnonKey = "sb_publishable_Jj5TIfWxCu2vbsaj9Uoneg_EZjYrkta";

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Supabase.initialize(url: supabaseUrl, publishableKey: supabaseAnonKey);
  runApp(const BrandBisnisApp());
}

class BrandBisnisApp extends StatelessWidget {
  const BrandBisnisApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "BrandBisnis V5.0",
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: const RootScreen(),
    );
  }
}

class RootScreen extends StatelessWidget {
  const RootScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final signedOut = Supabase.instance.client.auth.currentSession == null;
    return StreamBuilder<bool>(
      initialData: signedOut,
      stream: Supabase.instance.client.auth.onAuthStateChange.map(
        (state) => state.session == null,
      ),
      builder: (context, snapshot) {
        return (snapshot.data ?? signedOut) ? const AuthScreen() : const MainShell();
      },
    );
  }
}
