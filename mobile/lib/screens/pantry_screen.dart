import 'package:flutter/material.dart';

import '../api_service.dart';
import '../pantry_api.dart';
import 'catalog_screen.dart';

/// "Dolabım": SKT'si en yakın olan en üstte.
class PantryScreen extends StatefulWidget {
  const PantryScreen({super.key});

  @override
  State<PantryScreen> createState() => _PantryScreenState();
}

class _PantryScreenState extends State<PantryScreen> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final items = await PantryApi.pantry();
      if (mounted) setState(() => _items = items);
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _showError(Object e) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(errorMessage(e))));
  }

  Future<void> _open(Map<String, dynamic> item) async {
    try {
      await PantryApi.open(item['id']);
      await _load();
    } catch (e) {
      if (mounted) _showError(e);
    }
  }

  Future<void> _thaw(Map<String, dynamic> item) async {
    try {
      await PantryApi.thaw(item['id']);
      await _load();
    } catch (e) {
      if (mounted) _showError(e);
    }
  }

  Future<void> _delete(Map<String, dynamic> item) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Ürünü sil'),
        content: Text('${item['name']} dolabından silinsin mi?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Vazgeç')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Sil')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await PantryApi.delete(item['id']);
      await _load();
    } catch (e) {
      if (mounted) _showError(e);
    }
  }

  Future<void> _goToCatalog() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CatalogScreen()));
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dolabım')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _goToCatalog,
        icon: const Icon(Icons.add),
        label: const Text('Ürün ekle'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(onRefresh: _load, child: _buildList()),
    );
  }

  Widget _buildList() {
    if (_error != null || _items.isEmpty) {
      // RefreshIndicator'ın çalışması için kaydırılabilir olmalı
      return ListView(
        children: [
          const SizedBox(height: 160),
          Icon(_error != null ? Icons.cloud_off : Icons.kitchen, size: 64, color: Colors.grey),
          const SizedBox(height: 12),
          Text(
            _error ?? 'Dolabın boş.\nÜrün eklemek için "Ürün ekle"ye bas.',
            textAlign: TextAlign.center,
          ),
        ],
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 96),
      itemCount: _items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, i) {
        final item = _items[i];
        final color = Color(expiryColorValue(item));
        final canOpen = item['storage'] == 'packaged' && item['opened'] != true;
        final frozen = item['frozen'] == true;
        return Card(
          margin: EdgeInsets.zero,
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: color.withValues(alpha: 0.15),
              child: Icon(
                frozen
                    ? Icons.ac_unit
                    : (item['storage'] == 'fresh' ? Icons.eco : Icons.inventory_2),
                color: color,
              ),
            ),
            title: Text(item['name']),
            subtitle: Text(
              expiryText(item),
              style: TextStyle(color: color, fontWeight: FontWeight.w600),
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (canOpen)
                  OutlinedButton(onPressed: () => _open(item), child: const Text('Açıldı')),
                if (frozen)
                  OutlinedButton(onPressed: () => _thaw(item), child: const Text('Çözdür')),
                IconButton(
                  tooltip: 'Sil',
                  icon: const Icon(Icons.delete_outline),
                  onPressed: () => _delete(item),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}