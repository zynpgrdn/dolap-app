import 'package:flutter/material.dart';

import '../api_service.dart';
import '../pantry_api.dart';

String _trLower(String s) => s.replaceAll('I', 'ı').replaceAll('İ', 'i').toLowerCase();

String _formatDate(DateTime d) =>
    '${d.day.toString().padLeft(2, '0')}.${d.month.toString().padLeft(2, '0')}.${d.year}';

/// Getir benzeri ürün ekleme ekranı: üstte arama, kategoriler, altta ürün kartları.
class CatalogScreen extends StatefulWidget {
  const CatalogScreen({super.key});

  @override
  State<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends State<CatalogScreen> {
  final _search = TextEditingController();
  List<Map<String, dynamic>> _categories = [];
  List<Map<String, dynamic>> _products = [];
  String? _selectedCategory;
  String _query = '';
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await PantryApi.catalog();
      final categories = List<Map<String, dynamic>>.from(
          (data['categories'] as List).map((e) => Map<String, dynamic>.from(e as Map)));
      final products = List<Map<String, dynamic>>.from(
          (data['products'] as List).map((e) => Map<String, dynamic>.from(e as Map)));
      products.sort((a, b) => _trLower(a['name']).compareTo(_trLower(b['name'])));
      setState(() {
        _categories = categories;
        _products = products;
        _selectedCategory = categories.isNotEmpty ? categories.first['id'] : null;
      });
    } catch (e) {
      setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _emojiOf(String categoryId) =>
      _categories.firstWhere((c) => c['id'] == categoryId, orElse: () => {'emoji': '🛒'})['emoji'];

  List<Map<String, dynamic>> get _visibleProducts {
    if (_query.isNotEmpty) {
      final q = _trLower(_query);
      return _products.where((p) => _trLower(p['name']).contains(q)).toList();
    }
    return _products.where((p) => p['category'] == _selectedCategory).toList();
  }

  Future<void> _add(Map<String, dynamic> product) async {
    final result = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _AddProductSheet(product: product),
    );
    if (result == null || !mounted) return;
    try {
      await PantryApi.add(
        product['id'],
        purchasedAt: result['purchased_at'],
        opened: result['opened'] ?? false,
        frozen: result['frozen'] ?? false,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('${product['name']} dolabına eklendi')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(errorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ürün ekle')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? _ErrorView(message: _error!, onRetry: _load)
          : Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: TextField(
              controller: _search,
              decoration: InputDecoration(
                hintText: 'Ürün ara (ör. domates)',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _query.isEmpty
                    ? null
                    : IconButton(
                  icon: const Icon(Icons.clear),
                  onPressed: () {
                    _search.clear();
                    setState(() => _query = '');
                  },
                ),
                border: const OutlineInputBorder(),
                isDense: true,
              ),
              onChanged: (v) => setState(() => _query = v.trim()),
            ),
          ),
          if (_query.isEmpty) _buildCategoryBar(),
          const Divider(height: 1),
          Expanded(child: _buildProducts()),
        ],
      ),
    );
  }

  Widget _buildCategoryBar() {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 104,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        itemCount: _categories.length,
        itemBuilder: (context, i) {
          final c = _categories[i];
          final selected = c['id'] == _selectedCategory;
          return GestureDetector(
            onTap: () => setState(() => _selectedCategory = c['id']),
            child: SizedBox(
              width: 80,
              child: Column(
                children: [
                  const SizedBox(height: 6),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 150),
                    width: 56,
                    height: 56,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: selected ? scheme.primaryContainer : scheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: selected ? scheme.primary : Colors.transparent,
                        width: 2,
                      ),
                    ),
                    child: Text(c['emoji'] ?? '', style: const TextStyle(fontSize: 26)),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    c['name'],
                    maxLines: 2,
                    textAlign: TextAlign.center,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildProducts() {
    final products = _visibleProducts;
    if (products.isEmpty) {
      return const Center(child: Text('Ürün bulunamadı.'));
    }

    // Alt gruplara ayır: gruba ait olmayanlar önce, sonra "Tavuk", "Kırmızı Et", "Peynir"...
    final groups = <String?, List<Map<String, dynamic>>>{};
    for (final p in products) {
      groups.putIfAbsent(_query.isEmpty ? p['group'] as String? : null, () => []).add(p);
    }
    final keys = groups.keys.toList()
      ..sort((a, b) => a == null ? -1 : (b == null ? 1 : a.compareTo(b)));

    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
      children: [
        for (final key in keys) ...[
          if (key != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 12, 4, 6),
              child: Text(key, style: Theme.of(context).textTheme.titleMedium),
            ),
          GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
            childAspectRatio: 0.9,
            children: [for (final p in groups[key]!) _productCard(p)],
          ),
        ],
      ],
    );
  }

  Widget _productCard(Map<String, dynamic> p) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => _add(p),
        child: Stack(
          children: [
            Padding(
              padding: const EdgeInsets.all(8),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(_emojiOf(p['category']), style: const TextStyle(fontSize: 30)),
                  const SizedBox(height: 6),
                  Text(
                    p['name'],
                    maxLines: 2,
                    textAlign: TextAlign.center,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13),
                  ),
                ],
              ),
            ),
            Positioned(
              top: 4,
              right: 4,
              child: Container(
                decoration: BoxDecoration(color: scheme.primary, borderRadius: BorderRadius.circular(8)),
                child: Icon(Icons.add, size: 20, color: scheme.onPrimary),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Ürüne dokununca açılan alt pencere: taze üründe alış tarihi, paketlide "açık mı?".
class _AddProductSheet extends StatefulWidget {
  final Map<String, dynamic> product;
  const _AddProductSheet({required this.product});

  @override
  State<_AddProductSheet> createState() => _AddProductSheetState();
}
class _AddProductSheetState extends State<_AddProductSheet> {
  DateTime _purchasedAt = DateTime.now();
  bool _opened = false;
  bool _frozen = false;

  bool get _isFresh => widget.product['storage'] == 'fresh';
  bool get _canFreeze => ['meat', 'seafood'].contains(widget.product['category']);

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _purchasedAt,
      firstDate: now.subtract(const Duration(days: 60)),
      lastDate: now,
      helpText: 'Alış tarihi',
    );
    if (picked != null) setState(() => _purchasedAt = picked);
  }

  @override
  Widget build(BuildContext context) {
    final days = widget.product['shelf_life_days'];
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(widget.product['name'], style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 4),
            Text(
              _isFresh
                  ? 'Taze ürün · alındıktan sonra yaklaşık $days gün dayanır'
                  : 'Paketli ürün · açıldıktan sonra yaklaşık $days gün dayanır',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            if (_isFresh)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.calendar_today),
                title: const Text('Alış tarihi'),
                subtitle: Text(_formatDate(_purchasedAt)),
                trailing: const Icon(Icons.edit),
                onTap: _pickDate,
              ),
            if (_isFresh && _canFreeze)
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                secondary: const Icon(Icons.ac_unit),
                title: const Text('Dondurucuya koydum'),
                subtitle: const Text('Dondurucuda yaklaşık 90 gün dayanır. Çıkarınca "Çözdür"e bas.'),
                value: _frozen,
                onChanged: (v) => setState(() => _frozen = v),
              ),
            if (!_isFresh)
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Paketi zaten açık'),
                subtitle: const Text('Açık değilse SKT sayacı "Açıldı" butonuna basınca başlar.'),
                value: _opened,
                onChanged: (v) => setState(() => _opened = v),
              ),
            const SizedBox(height: 16),
            FilledButton.icon(
              icon: const Icon(Icons.kitchen),
              label: const Text('Dolabıma ekle'),
              onPressed: () => Navigator.of(context).pop({
                'purchased_at': _isFresh ? _purchasedAt : null,
                'opened': _opened,
                'frozen': _isFresh && _canFreeze && _frozen,
              }),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            OutlinedButton(onPressed: onRetry, child: const Text('Tekrar dene')),
          ],
        ),
      ),
    );
  }
}