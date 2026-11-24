String? validateRequired(String? value, String fieldName) =>
    (value == null || value.trim().isEmpty) ? '$fieldName boş olamaz' : null;

String? validateEmail(String? value) {
  if (value == null || value.trim().isEmpty) return 'E-posta boş olamaz';
  final isValid = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(value.trim());
  return isValid ? null : 'Geçerli bir e-posta girin';
}

String? validatePassword(String? value) {
  if (value == null || value.isEmpty) return 'Şifre boş olamaz';
  if (value.length < 6) return 'Şifre en az 6 karakter olmalı';
  return null;
}