import 'dart:async';
import 'package:flutter/material.dart';

class MyWidget extends StatelessWidget {
  final String title;

  const MyWidget({required this.title});

  @override
  Widget build(BuildContext context) {
    return Container(child: Text(title));
  }

  void _refresh() {
    print('refreshing');
  }
}

mixin Loggable {
  void log(String message) {
    print(message);
  }
}

enum Status { active, inactive, pending }

extension StringExt on String {
  bool get isBlank => trim().isEmpty;
}

void main() {
  runApp(MyWidget(title: 'Hello'));
}

Future<int> fetchData(String url) async {
  await Future.delayed(Duration(seconds: 1));
  return 42;
}
