import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'api_service.dart';
import 'navigation.dart';
import 'screens/login_screen.dart';
import 'theme.dart';

void main() => runApp(const DolApp());

class DolApp extends StatelessWidget {
  const DolApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DolApp',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      // Takvim, "İptal/Tamam" butonları vb. Türkçe olsun
      locale: const Locale('tr', 'TR'),
      supportedLocales: const [Locale('tr', 'TR')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const StartupScreen(),
    );
  }
}

/// Açılışta kayıtlı oturum var mı diye bakar.
class StartupScreen extends StatefulWidget {
  const StartupScreen({super.key});

  @override
  State<StartupScreen> createState() => _StartupScreenState();
}

class _StartupScreenState extends State<StartupScreen> {
  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check() async {
    Map<String, dynamic>? user;
    try {
      user = await ApiService.me();
    } catch (_) {
      user = null;
    }
    if (!mounted) return;
    final target = user == null ? const LoginScreen() : homeForUser(user);
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => target));
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: CircularProgressIndicator()));
  }
}