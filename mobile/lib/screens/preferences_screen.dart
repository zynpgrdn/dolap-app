import 'package:flutter/material.dart';

import '../api_service.dart';
import 'login_screen.dart';

class PreferencesScreen extends StatelessWidget {
  final Map<String, dynamic> user;
  const PreferencesScreen({super.key, required this.user});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Tercihlerin')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Hoş geldin ${user['first_name']}!',
                style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 12),
            const Text('Alerjen ve beslenme tercihi seçimi bir sonraki adımda buraya gelecek.'),
            const Spacer(),
            OutlinedButton(
              onPressed: () async {
                await ApiService.logout();
                if (!context.mounted) return;
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                      (_) => false,
                );
              },
              child: const Text('Çıkış yap'),
            ),
          ],
        ),
      ),
    );
  }
}