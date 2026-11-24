import 'package:flutter/material.dart';

import '../api_service.dart';
import 'login_screen.dart';

class HomeScreen extends StatelessWidget {
  final Map<String, dynamic> user;
  const HomeScreen({super.key, required this.user});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Merhaba ${user['first_name']}')),
      body: const Center(child: Text('Ana sayfa yakında')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await ApiService.logout();
          if (!context.mounted) return;
          Navigator.of(context).pushAndRemoveUntil(
            MaterialPageRoute(builder: (_) => const LoginScreen()),
                (_) => false,
          );
        },
        icon: const Icon(Icons.logout),
        label: const Text('Çıkış'),
      ),
    );
  }
}