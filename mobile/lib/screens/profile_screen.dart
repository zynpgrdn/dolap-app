import 'package:flutter/material.dart';

import '../api_service.dart';
import '../theme.dart';
import 'login_screen.dart';

class ProfileScreen extends StatelessWidget {
  final Map<String, dynamic> user;
  const ProfileScreen({super.key, required this.user});

  Future<void> _logout(BuildContext context) async {
    await ApiService.logout();
    if (!context.mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
          (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final firstName = (user['first_name'] ?? '').toString();
    final lastName = (user['last_name'] ?? '').toString();
    final email = (user['email'] ?? '').toString();
    final initial = firstName.isNotEmpty ? firstName[0].toUpperCase() : '?';

    return Scaffold(
      appBar: AppBar(title: const Text('Profil')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: CircleAvatar(child: Text(initial)),
              title: Text('$firstName $lastName'),
              subtitle: Text(email),
            ),
          ),
          const SizedBox(height: 16),
          const Card(
            child: ListTile(
              leading: Icon(Icons.no_food_outlined),
              title: Text('Alerjen ve beslenme tercihleri'),
              subtitle: Text('Yakında'),
              enabled: false,
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.logout, color: AppColors.danger),
              title: const Text('Çıkış yap', style: TextStyle(color: AppColors.danger)),
              onTap: () => _logout(context),
            ),
          ),
        ],
      ),
    );
  }
}