import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'config.dart';

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

String errorMessage(Object e) =>
    e is ApiException ? e.message : 'Sunucuya bağlanılamadı. Backend çalışıyor mu?';

class ApiService {
  static const _storage = FlutterSecureStorage();
  static const _tokenKey = 'token';
  static const _timeout = Duration(seconds: 10);

  static Future<String?> readToken() => _storage.read(key: _tokenKey);
  static Future<void> _saveToken(String t) => _storage.write(key: _tokenKey, value: t);
  static Future<void> logout() => _storage.delete(key: _tokenKey);

  static Map<String, dynamic> _parse(http.Response r) {
    final body = r.body.isEmpty ? {} : jsonDecode(utf8.decode(r.bodyBytes));
    if (r.statusCode >= 200 && r.statusCode < 300) {
      return Map<String, dynamic>.from(body as Map);
    }
    final detail = body is Map ? body['detail'] : null;
    if (detail is String) throw ApiException(detail);
    throw ApiException('Bilgileri kontrol edin (hata ${r.statusCode}).');
  }

  static Future<Map<String, String>> _authHeaders() async {
    final token = await readToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  static Future<http.Response> _post(String path, Map<String, dynamic> body) {
    return http
        .post(
      Uri.parse('$apiBaseUrl$path'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    )
        .timeout(_timeout);
  }

  static Future<Map<String, dynamic>> register({
    required String firstName,
    required String lastName,
    required String email,
    required String password,
  }) async {
    final data = _parse(await _post('/register', {
      'first_name': firstName,
      'last_name': lastName,
      'email': email,
      'password': password,
    }));
    await _saveToken(data['token']);
    return Map<String, dynamic>.from(data['user']);
  }

  static Future<Map<String, dynamic>> login(String email, String password) async {
    final data = _parse(await _post('/login', {'email': email, 'password': password}));
    await _saveToken(data['token']);
    return Map<String, dynamic>.from(data['user']);
  }

  /// Kayıtlı token varsa kullanıcıyı döndürür, yoksa ya da geçersizse null.
  static Future<Map<String, dynamic>?> me() async {
    final token = await readToken();
    if (token == null) return null;
    final r = await http.get(
      Uri.parse('$apiBaseUrl/me'),
      headers: {'Authorization': 'Bearer $token'},
    ).timeout(_timeout);
    if (r.statusCode == 401) {
      await logout();
      return null;
    }
    return _parse(r);
  }

  static Future<Map<String, dynamic>> verifyEmail(String code) async {
    final r = await http
        .post(
      Uri.parse('$apiBaseUrl/verify-email'),
      headers: await _authHeaders(),
      body: jsonEncode({'code': code}),
    )
        .timeout(_timeout);
    return _parse(r);
  }

  static Future<String> resendCode() async {
    final r = await http
        .post(Uri.parse('$apiBaseUrl/resend-code'), headers: await _authHeaders())
        .timeout(_timeout);
    return _parse(r)['message'] as String;
  }
}