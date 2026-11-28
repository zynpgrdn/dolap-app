import 'package:flutter/material.dart';

import 'screens/main_shell.dart';
import 'screens/preferences_screen.dart';
import 'screens/verify_email_screen.dart';

/// Önce e-posta doğrulaması, sonra tercihler, en son ana sayfa.
Widget homeForUser(Map<String, dynamic> user) {
  if (user['email_verified'] != true) return VerifyEmailScreen(user: user);
  if (user['preferences_completed'] != true) return PreferencesScreen(user: user);
  return MainShell(user: user);
}