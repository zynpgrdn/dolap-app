import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_service.dart';
import 'config.dart';

/// Katalog ve dolap uç noktaları.
class PantryApi {
  static const _timeout = Duration(seconds: 10);

  static Future<dynamic> _send(String method, String path, [Map<String, dynamic>? body]) async {
    final token = await ApiService.readToken();
    final request = http.Request(method, Uri.parse('$apiBaseUrl$path'))
      ..headers['Content-Type'] = 'application/json';
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    if (body != null) request.body = jsonEncode(body);

    final response = await http.Response.fromStream(await request.send().timeout(_timeout));
    final data = response.body.isEmpty ? null : jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode >= 200 && response.statusCode < 300) return data;
    final detail = data is Map ? data['detail'] : null;
    throw ApiException(detail is String ? detail : 'Bir hata oluştu (hata ${response.statusCode}).');
  }

  static List<Map<String, dynamic>> _list(dynamic data) =>
      (data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();

  /// {categories: [...], products: [...]}
  static Future<Map<String, dynamic>> catalog() async =>
      Map<String, dynamic>.from(await _send('GET', '/catalog') as Map);

  static Future<List<Map<String, dynamic>>> pantry() async => _list(await _send('GET', '/pantry'));

  static Future<Map<String, dynamic>> add(String productId,
      {DateTime? purchasedAt, bool opened = false, bool frozen = false}) async {
    final data = await _send('POST', '/pantry', {
      'product_id': productId,
      if (purchasedAt != null) 'purchased_at': purchasedAt.toIso8601String().substring(0, 10),
      'opened': opened,
      'frozen': frozen,
    });
    return Map<String, dynamic>.from(data as Map);
  }

  static Future<void> open(String itemId) => _send('POST', '/pantry/$itemId/open');

  static Future<void> thaw(String itemId) => _send('POST', '/pantry/$itemId/thaw');

  static Future<void> delete(String itemId) => _send('DELETE', '/pantry/$itemId');

  /// {expired: [...], expiring_soon: [...]}
  static Future<Map<String, List<Map<String, dynamic>>>> alerts() async {
    final data = await _send('GET', '/alerts') as Map;
    return {
      'expired': _list(data['expired']),
      'expiring_soon': _list(data['expiring_soon']),
    };
  }
}

/// "3 gün kaldı", "Bugün son gün", "Süresi 2 gün önce geçti" ...
String expiryText(Map<String, dynamic> item) {
  final days = item['days_left'] as int?;
  if (days == null) return 'Açılmadı · SKT açınca başlar';
  if (days < 0) return 'Süresi ${-days} gün önce geçti';
  if (item['frozen'] == true) return 'Dondurucuda · $days gün kaldı';
  if (days == 0) return 'Bugün son gün';
  if (days == 1) return 'Yarın son gün';
  return '$days gün kaldı';
}

/// Kırmızı: geçmiş, turuncu: yaklaşıyor, gri: açılmamış, mavi: dondurucuda, yeşil: sorun yok.
int expiryColorValue(Map<String, dynamic> item) {
  if (item['expired'] == true) return 0xFFD32F2F;
  if (item['expiring_soon'] == true) return 0xFFF57C00;
  if (item['days_left'] == null) return 0xFF9E9E9E;
  if (item['frozen'] == true) return 0xFF1976D2;
  return 0xFF388E3C;
}