import 'package:flutter/material.dart';

import '../api_service.dart';
import '../pantry_api.dart';
import 'catalog_screen.dart';
import 'login_screen.dart';
import 'pantry_screen.dart';

class HomeScreen extends StatefulWidget {
  final Map<String, dynamic> user;
  const HomeScreen({super.key, required this.user});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<Map<String, dynamic>> _expired = [];
  List<Map<String, dynamic>> _expiringSoon = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadAlerts();
  }

  Future<void> _loadAlerts() async {
    setState(() => _error = null);
    try {
      final alerts = await PantryApi.alerts();
      if (!mounted) return;
      setState(() {
        _expired = alerts['expired']!;
        _expiringSoon = alerts['expiring_soon']!;
      });
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _open(Widget screen) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => screen));
    await _loadAlerts();
  }

  Future<void> _logout() async {
    await ApiService.logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
          (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('DolApp'),
        actions: [
          IconButton(tooltip: 'Çıkış yap', icon: const Icon(Icons.logout), onPressed: _logout),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadAlerts,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text('Merhaba ${widget.user['first_name']} 👋', style: text.headlineSmall),
            const SizedBox(height: 16),
            _buildAlertsCard(),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _ActionTile(
                    icon: Icons.kitchen,
                    label: 'Dolabım',
                    onTap: () => _open(const PantryScreen()),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionTile(
                    icon: Icons.add_shopping_cart,
                    label: 'Ürün ekle',
                    onTap: () => _open(const CatalogScreen()),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Card(
              child: ListTile(
                leading: const Icon(Icons.restaurant_menu),
                title: const Text('Tarif önerileri'),
                subtitle: const Text('Yakında'),
                enabled: false,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAlertsCard() {
    if (_loading) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }
    if (_error != null) {
      return Card(
        child: ListTile(
          leading: const Icon(Icons.cloud_off),
          title: Text(_error!),
          trailing: IconButton(icon: const Icon(Icons.refresh), onPressed: _loadAlerts),
        ),
      );
    }
    if (_expired.isEmpty && _expiringSoon.isEmpty) {
      return const Card(
        child: ListTile(
          leading: Icon(Icons.check_circle, color: Colors.green),
          title: Text('Her şey yolunda'),
          subtitle: Text('SKT\'si yaklaşan ürünün yok.'),
        ),
      );
    }
    final items = [..._expired, ..._expiringSoon];
    return Card(
      color: Theme.of(context).colorScheme.errorContainer.withValues(alpha: 0.5),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const ListTile(
              leading: Icon(Icons.warning_amber_rounded, color: Colors.orange),
              title: Text('SKT uyarısı', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            for (final item in items)
              ListTile(
                dense: true,
                title: Text(item['name']),
                trailing: Text(
                  expiryText(item),
                  style: TextStyle(
                    color: Color(expiryColorValue(item)),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _ActionTile({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: scheme.primaryContainer,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 24),
          child: Column(
            children: [
              Icon(icon, size: 36, color: scheme.onPrimaryContainer),
              const SizedBox(height: 8),
              Text(label,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: scheme.onPrimaryContainer,
                  )),
            ],
          ),
        ),
      ),
    );
  }
}