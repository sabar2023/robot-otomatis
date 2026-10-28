import 'package:flutter_test/flutter_test.dart';
import 'package:brandbisnis_app/main.dart' show supabaseUrl;

void main() {
  test('supabase url terbentuk', () {
    expect(supabaseUrl, startsWith("https://"));
  });
}
