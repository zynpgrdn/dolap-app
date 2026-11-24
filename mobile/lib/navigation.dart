import 'package:flutter/material.dart';

import 'screens/home_screen.dart';
import 'screens/preferences_screen.dart';

/// Alerjen ve beslenme tercihini henüz girmediyse önce tercihler ekranına gider.
Widget homeForUser(Map<String, dynamic> user) =>
    user['preferences_completed'] == true
        ? HomeScreen(user: user)
        : PreferencesScreen(user: user);