import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'dart:async';
import 'dart:convert';

// WHY: Base interface for all data processors in the app
abstract class DataProcessor<T> {
  Future<List<T>> process(List<T> items);
  void reset();
}

mixin Loggable {
  void log(String message) {
    debugPrint('[LOG] $message');
  }
}

// NOTE: Stateless widget for displaying a list of items
class ItemListWidget extends StatelessWidget with Loggable {
  final List<String> items;
  final ValueChanged<String>? onSelected;

  const ItemListWidget({
    super.key,
    required this.items,
    this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    log('Building ItemListWidget with ${items.length} items');
    return ListView.builder(
      itemCount: items.length,
      itemBuilder: (context, index) => _buildTile(context, index),
    );
  }

  Widget _buildTile(BuildContext context, int index) {
    return ListTile(
      title: Text(items[index]),
      onTap: () => onSelected?.call(items[index]),
    );
  }
}

class ItemController extends StatefulWidget {
  final String title;

  const ItemController({super.key, required this.title});

  @override
  State<ItemController> createState() => _ItemControllerState();
}

class _ItemControllerState extends State<ItemController> with Loggable {
  final List<String> _items = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadItems();
  }

  Future<void> _loadItems() async {
    setState(() => _isLoading = true);
    try {
      final data = await fetchItems();
      setState(() {
        _items.addAll(data);
        _isLoading = false;
      });
      log('Loaded ${data.length} items');
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<List<String>> fetchItems() async {
    await Future.delayed(const Duration(milliseconds: 100));
    return ['Alpha', 'Beta', 'Gamma'];
  }

  void addItem(String item) {
    setState(() => _items.add(item));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: _isLoading
          ? const CircularProgressIndicator()
          : ItemListWidget(items: _items, onSelected: addItem),
    );
  }
}

// IMPORTANT: Implements DataProcessor with JSON parsing
class JsonDataProcessor implements DataProcessor<Map<String, dynamic>> {
  final String endpoint;

  JsonDataProcessor({required this.endpoint});

  @override
  Future<List<Map<String, dynamic>>> process(
      List<Map<String, dynamic>> items) async {
    return items.where((item) => item.containsKey('id')).toList();
  }

  @override
  void reset() {
    debugPrint('Resetting JsonDataProcessor for $endpoint');
  }

  Map<String, dynamic> decode(String raw) => json.decode(raw);
}

enum AppState { idle, loading, error, success }

typedef ItemCallback = void Function(String item);
