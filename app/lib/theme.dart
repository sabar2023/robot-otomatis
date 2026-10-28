import 'package:flutter/material.dart';

const bgDeep = Color(0xFF03181F);
const bgPanel = Color(0xFF0A333E);
const bgPanelLight = Color(0xFF0F4653);
const accentMain = Color(0xFF2DD4BF);
const accentSoft = Color(0xFF99F6E4);
const textMain = Color(0xFFE6FBF7);
const textMuted = Color(0xFF7FB8B0);
const dangerMain = Color(0xFFF87171);
const upColor = Color(0xFF4ADE80);
const downColor = Color(0xFFF87171);

ThemeData buildTheme() {
  final base = ThemeData(brightness: Brightness.dark, useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: bgDeep,
    colorScheme: const ColorScheme.dark(
      primary: accentMain,
      secondary: accentSoft,
      surface: bgPanel,
      error: dangerMain,
    ),
    textTheme: base.textTheme.apply(bodyColor: textMain, displayColor: textMain),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      centerTitle: true,
      titleTextStyle: TextStyle(color: accentSoft, fontSize: 18, fontWeight: FontWeight.w700),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: accentMain,
        foregroundColor: bgDeep,
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: accentSoft,
        side: const BorderSide(color: accentMain, width: 1.2),
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
    ),
    switchTheme: const SwitchThemeData(
      thumbColor: WidgetStatePropertyAll(Color(0xFF02222B)),
      trackColor: WidgetStatePropertyAll(bgPanelLight),
    ),
    dividerTheme: const DividerThemeData(color: Color(0xFF10404C), thickness: 1),
  );
}

Widget panelCard({required Widget child, EdgeInsetsGeometry padding = const EdgeInsets.all(20)}) {
  return Container(
    margin: const EdgeInsets.fromLTRB(16, 6, 16, 10),
    padding: padding,
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(22),
      border: Border.all(color: const Color(0x1FFFFFFF)),
      boxShadow: const [
        BoxShadow(color: Color(0x59000000), blurRadius: 18, offset: Offset(0, 10)),
      ],
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFF0E4450), bgPanel],
        stops: [0.0, 0.6],
      ),
    ),
    child: child,
  );
}

InputDecoration appDecoration({String? label, String? hintText, bool filled = true}) {
  return InputDecoration(
    labelText: label,
    hintText: hintText,
    filled: filled,
    fillColor: const Color(0xFF062830),
    contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFF155E6E)),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFF155E6E)),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: accentMain, width: 1.6),
    ),
    errorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: dangerMain),
    ),
    focusedErrorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: dangerMain, width: 1.6),
    ),
  );
}
