import 'package:flutter/material.dart';

import 'home_screen.dart';
import 'pantry_screen.dart';
import 'profile_screen.dart';

/// Girişten sonraki ana iskelet: alt menü + sekmeler.
class MainShell extends StatefulWidget {
  final Map<String, dynamic> user;
  const MainShell({super.key, required this.user});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  void _goTo(int i) => setState(() => _index = i);

  @override
  Widget build(BuildContext context) {
    final pages = [
      HomeScreen(user: widget.user, onGoToTab: _goTo),
      const PantryScreen(),
      const _ComingSoon(title: 'Tarifler', icon: Icons.restaurant_menu),
      const _ComingSoon(title: 'Asistan', icon: Icons.chat_bubble_outline),
      ProfileScreen(user: widget.user),
    ];

    return Scaffold(
      body: pages[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: _goTo,
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Ana Sayfa'),
          NavigationDestination(
              icon: Icon(Icons.kitchen_outlined), selectedIcon: Icon(Icons.kitchen), label: 'Dolabım'),
          NavigationDestination(icon: Icon(Icons.restaurant_menu), label: 'Tarifler'),
          NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline), selectedIcon: Icon(Icons.chat_bubble), label: 'Asistan'),
          NavigationDestination(
              icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Profil'),
        ],
      ),
    );
  }
}

/// Henüz yazılmamış sekmeler için geçici sayfa.
class _ComingSoon extends StatelessWidget {
  final String title;
  final IconData icon;
  const _ComingSoon({required this.title, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 64, color: Colors.grey),
            const SizedBox(height: 12),
            const Text('Yakında', style: TextStyle(color: Colors.grey, fontSize: 18)),
          ],
        ),
      ),
    );
  }
}