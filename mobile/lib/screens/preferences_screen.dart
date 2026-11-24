import 'package:flutter/material.dart';

import '../api_service.dart';
import '../navigation.dart';
import 'login_screen.dart';

const allergenLabels = {
  'gluten': 'Gluten',
  'lactose': 'Laktoz (süt)',
  'egg': 'Yumurta',
  'fish': 'Balık',
  'shellfish': 'Kabuklu deniz ürünleri',
  'peanut': 'Yer fıstığı',
  'almond': 'Badem',
  'hazelnut': 'Fındık',
  'walnut': 'Ceviz',
  'sesame': 'Susam',
  'soy': 'Soya',
};

const dietLabels = {
  'none': 'Hepsini yerim',
  'vegetarian': 'Vejetaryen',
  'vegan': 'Vegan',
};

const dietDescriptions = {
  'none': 'Et, balık ve hayvansal ürünler dahil her şey',
  'vegetarian': 'Et ve balık yok; süt, yumurta ve bal var',
  'vegan': 'Hiçbir hayvansal ürün yok (süt, yumurta ve bal dahil)',
};

class PreferencesScreen extends StatefulWidget {
  final Map<String, dynamic> user;
  const PreferencesScreen({super.key, required this.user});

  @override
  State<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends State<PreferencesScreen> {
  late final Set<String> _allergens;
  late String _diet;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _allergens = Set<String>.from(widget.user['allergens'] ?? const []);
    _diet = (widget.user['diet'] as String?) ?? 'none';
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final user = await ApiService.updatePreferences(
        allergens: _allergens.toList(),
        diet: _diet,
      );
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => homeForUser(user)),
            (_) => false,
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(errorMessage(e))));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
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
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tercihlerin'),
        actions: [
          IconButton(
            tooltip: 'Çıkış yap',
            icon: const Icon(Icons.logout),
            onPressed: _logout,
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Text('Hoş geldin ${widget.user['first_name']}!', style: textTheme.headlineSmall),
            const SizedBox(height: 8),
            const Text(
              'Sana uygun tarifleri önerebilmemiz için alerjenlerini ve beslenme tercihini seç. '
                  'Bunları daha sonra profilinden değiştirebilirsin.',
            ),
            const SizedBox(height: 24),
            Text('Alerjenlerin', style: textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilterChip(
                  label: const Text('Alerjim yok'),
                  selected: _allergens.isEmpty,
                  onSelected: (_) => setState(_allergens.clear),
                ),
                for (final entry in allergenLabels.entries)
                  FilterChip(
                    label: Text(entry.value),
                    selected: _allergens.contains(entry.key),
                    onSelected: (selected) => setState(() {
                      selected ? _allergens.add(entry.key) : _allergens.remove(entry.key);
                    }),
                  ),
              ],
            ),
            const SizedBox(height: 32),
            Text('Beslenme tercihin', style: textTheme.titleMedium),
            const SizedBox(height: 8),
            RadioGroup<String>(
              groupValue: _diet,
              onChanged: (value) {
                if (value != null) setState(() => _diet = value);
              },
              child: Column(
                children: [
                  for (final entry in dietLabels.entries)
                    RadioListTile<String>(
                      value: entry.key,
                      title: Text(entry.value),
                      subtitle: Text(dietDescriptions[entry.key]!),
                      contentPadding: EdgeInsets.zero,
                    ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Kaydet ve devam et'),
            ),
          ],
        ),
      ),
    );
  }
}