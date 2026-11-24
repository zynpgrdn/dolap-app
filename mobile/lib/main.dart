import 'package:flutter/material.dart';

import 'api_service.dart';
import 'navigation.dart';
import 'screens/login_screen.dart';

void main() => runApp(const DolapApp());

class DolapApp extends StatelessWidget {
  const DolapApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Dolap',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: Colors.green, useMaterial3: true),
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
    _checkSession();
  }

  Future<void> _checkSession() async {
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