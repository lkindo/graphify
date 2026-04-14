"""Tests for language extractors: Java, C, C++, Ruby, C#, Kotlin, Scala, PHP, Swift, Go, Julia."""
from __future__ import annotations
from pathlib import Path
import pytest
from graphify.extract import (
    extract_java, extract_c, extract_cpp, extract_ruby,
    extract_csharp, extract_kotlin, extract_scala, extract_php,
    extract_swift, extract_go, extract_julia, extract_ets,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _labels(r):
    return [n["label"] for n in r["nodes"]]

def _relations(r):
    return {e["relation"] for e in r["edges"]}

def _calls(r):
    node_by_id = {n["id"]: n["label"] for n in r["nodes"]}
    return {
        (node_by_id.get(e["source"], e["source"]), node_by_id.get(e["target"], e["target"]))
        for e in r["edges"] if e["relation"] == "calls"
    }


# ── Java ──────────────────────────────────────────────────────────────────────

def test_java_no_error():
    r = extract_java(FIXTURES / "sample.java")
    assert "error" not in r

def test_java_finds_class():
    r = extract_java(FIXTURES / "sample.java")
    assert any("DataProcessor" in l for l in _labels(r))

def test_java_finds_interface():
    r = extract_java(FIXTURES / "sample.java")
    assert any("Processor" in l for l in _labels(r))

def test_java_finds_methods():
    r = extract_java(FIXTURES / "sample.java")
    labels = _labels(r)
    assert any("addItem" in l for l in labels)
    assert any("process" in l for l in labels)

def test_java_finds_imports():
    r = extract_java(FIXTURES / "sample.java")
    assert "imports" in _relations(r)

def test_java_no_dangling_edges():
    r = extract_java(FIXTURES / "sample.java")
    node_ids = {n["id"] for n in r["nodes"]}
    for e in r["edges"]:
        assert e["source"] in node_ids


# ── C ────────────────────────────────────────────────────────────────────────

def test_c_no_error():
    r = extract_c(FIXTURES / "sample.c")
    assert "error" not in r

def test_c_finds_functions():
    r = extract_c(FIXTURES / "sample.c")
    labels = _labels(r)
    assert any("process" in l for l in labels)
    assert any("main" in l for l in labels)

def test_c_finds_includes():
    r = extract_c(FIXTURES / "sample.c")
    assert "imports" in _relations(r)

def test_c_emits_calls():
    r = extract_c(FIXTURES / "sample.c")
    assert any(e["relation"] == "calls" for e in r["edges"])

def test_c_calls_are_extracted():
    r = extract_c(FIXTURES / "sample.c")
    for e in r["edges"]:
        if e["relation"] == "calls":
            assert e["confidence"] == "EXTRACTED"


# ── C++ ───────────────────────────────────────────────────────────────────────

def test_cpp_no_error():
    r = extract_cpp(FIXTURES / "sample.cpp")
    assert "error" not in r

def test_cpp_finds_class():
    r = extract_cpp(FIXTURES / "sample.cpp")
    assert any("HttpClient" in l for l in _labels(r))

def test_cpp_finds_methods():
    r = extract_cpp(FIXTURES / "sample.cpp")
    labels = _labels(r)
    # C++ extractor captures the constructor and public-visible methods
    assert any("HttpClient" in l for l in labels)

def test_cpp_finds_includes():
    r = extract_cpp(FIXTURES / "sample.cpp")
    assert "imports" in _relations(r)


# ── Ruby ─────────────────────────────────────────────────────────────────────

def test_ruby_no_error():
    r = extract_ruby(FIXTURES / "sample.rb")
    assert "error" not in r

def test_ruby_finds_class():
    r = extract_ruby(FIXTURES / "sample.rb")
    assert any("ApiClient" in l for l in _labels(r))

def test_ruby_finds_methods():
    r = extract_ruby(FIXTURES / "sample.rb")
    labels = _labels(r)
    assert any("get" in l for l in labels)
    assert any("post" in l for l in labels)

def test_ruby_finds_function():
    r = extract_ruby(FIXTURES / "sample.rb")
    assert any("parse_response" in l for l in _labels(r))


# ── C# ───────────────────────────────────────────────────────────────────────

def test_csharp_no_error():
    r = extract_csharp(FIXTURES / "sample.cs")
    assert "error" not in r

def test_csharp_finds_class():
    r = extract_csharp(FIXTURES / "sample.cs")
    assert any("DataProcessor" in l for l in _labels(r))

def test_csharp_finds_interface():
    r = extract_csharp(FIXTURES / "sample.cs")
    assert any("IProcessor" in l for l in _labels(r))

def test_csharp_finds_methods():
    r = extract_csharp(FIXTURES / "sample.cs")
    labels = _labels(r)
    assert any("Process" in l for l in labels)

def test_csharp_finds_usings():
    r = extract_csharp(FIXTURES / "sample.cs")
    assert "imports" in _relations(r)

def test_csharp_inherits_edge():
    r = extract_csharp(FIXTURES / "sample.cs")
    inherits = [e for e in r["edges"] if e["relation"] == "inherits"]
    assert len(inherits) >= 1

def test_csharp_inherits_iprocessor():
    r = extract_csharp(FIXTURES / "sample.cs")
    node_by_id = {n["id"]: n["label"] for n in r["nodes"]}
    found = any(
        "DataProcessor" in node_by_id.get(e["source"], "") and
        "IProcessor" in node_by_id.get(e["target"], "")
        for e in r["edges"] if e["relation"] == "inherits"
    )
    assert found, "DataProcessor should have inherits edge to IProcessor"


# ── Kotlin ───────────────────────────────────────────────────────────────────

def test_kotlin_no_error():
    r = extract_kotlin(FIXTURES / "sample.kt")
    assert "error" not in r

def test_kotlin_finds_class():
    r = extract_kotlin(FIXTURES / "sample.kt")
    assert any("HttpClient" in l for l in _labels(r))

def test_kotlin_finds_data_class():
    r = extract_kotlin(FIXTURES / "sample.kt")
    assert any("Config" in l for l in _labels(r))

def test_kotlin_finds_methods():
    r = extract_kotlin(FIXTURES / "sample.kt")
    labels = _labels(r)
    assert any("get" in l for l in labels)
    assert any("post" in l for l in labels)

def test_kotlin_finds_function():
    r = extract_kotlin(FIXTURES / "sample.kt")
    assert any("createClient" in l for l in _labels(r))


# ── Scala ─────────────────────────────────────────────────────────────────────

def test_scala_no_error():
    r = extract_scala(FIXTURES / "sample.scala")
    assert "error" not in r

def test_scala_finds_class():
    r = extract_scala(FIXTURES / "sample.scala")
    assert any("HttpClient" in l for l in _labels(r))

def test_scala_finds_object():
    r = extract_scala(FIXTURES / "sample.scala")
    assert any("HttpClientFactory" in l for l in _labels(r))

def test_scala_finds_methods():
    r = extract_scala(FIXTURES / "sample.scala")
    labels = _labels(r)
    assert any("get" in l for l in labels)
    assert any("post" in l for l in labels)


# ── PHP ───────────────────────────────────────────────────────────────────────

def test_php_no_error():
    r = extract_php(FIXTURES / "sample.php")
    assert "error" not in r

def test_php_finds_class():
    r = extract_php(FIXTURES / "sample.php")
    assert any("ApiClient" in l for l in _labels(r))

def test_php_finds_methods():
    r = extract_php(FIXTURES / "sample.php")
    labels = _labels(r)
    assert any("get" in l for l in labels)
    assert any("post" in l for l in labels)

def test_php_finds_function():
    r = extract_php(FIXTURES / "sample.php")
    assert any("parseResponse" in l for l in _labels(r))

def test_php_finds_imports():
    r = extract_php(FIXTURES / "sample.php")
    assert "imports" in _relations(r)

def test_php_finds_static_property_access():
    r = extract_php(FIXTURES / "sample_php_static_prop.php")
    assert "uses_static_prop" in _relations(r)

def test_php_static_prop_target_is_holding_class():
    r = extract_php(FIXTURES / "sample_php_static_prop.php")
    node_by_id = {n["id"]: n["label"] for n in r["nodes"]}
    uses_prop = [
        (node_by_id.get(e["source"], e["source"]), node_by_id.get(e["target"], e["target"]))
        for e in r["edges"] if e["relation"] == "uses_static_prop"
    ]
    assert any("DefaultPalette" in tgt for _, tgt in uses_prop)

def test_php_finds_config_helper_call():
    r = extract_php(FIXTURES / "sample_php_config.php")
    assert "uses_config" in _relations(r)

def test_php_config_helper_target_matches_first_segment():
    r = extract_php(FIXTURES / "sample_php_config.php")
    node_by_id = {n["id"]: n["label"] for n in r["nodes"]}
    uses_cfg = [
        (node_by_id.get(e["source"], e["source"]), node_by_id.get(e["target"], e["target"]))
        for e in r["edges"] if e["relation"] == "uses_config"
    ]
    assert any("Throttle" in tgt for _, tgt in uses_cfg)

def test_php_finds_container_bind():
    r = extract_php(FIXTURES / "sample_php_container.php")
    assert "bound_to" in _relations(r)

def test_php_container_bind_links_contract_to_implementation():
    r = extract_php(FIXTURES / "sample_php_container.php")
    node_by_id = {n["id"]: n["label"] for n in r["nodes"]}
    bound = [
        (node_by_id.get(e["source"], e["source"]), node_by_id.get(e["target"], e["target"]))
        for e in r["edges"] if e["relation"] == "bound_to"
    ]
    assert any("PaymentGateway" in src and "StripeGateway" in tgt for src, tgt in bound)

def test_php_finds_event_listeners():
    r = extract_php(FIXTURES / "sample_php_listen.php")
    assert "listened_by" in _relations(r)

def test_php_event_listener_links_event_to_listener():
    r = extract_php(FIXTURES / "sample_php_listen.php")
    node_by_id = {n["id"]: n["label"] for n in r["nodes"]}
    listened = [
        (node_by_id.get(e["source"], e["source"]), node_by_id.get(e["target"], e["target"]))
        for e in r["edges"] if e["relation"] == "listened_by"
    ]
    assert any("UserRegistered" in src and "SendWelcomeEmail" in tgt for src, tgt in listened)


# ── Swift ────────────────────────────────────────────────────────────────────

def test_swift_no_error():
    r = extract_swift(FIXTURES / "sample.swift")
    assert "error" not in r

def test_swift_finds_class():
    r = extract_swift(FIXTURES / "sample.swift")
    assert any("DataProcessor" in l for l in _labels(r))

def test_swift_finds_protocol():
    r = extract_swift(FIXTURES / "sample.swift")
    assert any("Processor" in l for l in _labels(r))

def test_swift_finds_struct():
    r = extract_swift(FIXTURES / "sample.swift")
    assert any("Config" in l for l in _labels(r))

def test_swift_finds_methods():
    r = extract_swift(FIXTURES / "sample.swift")
    labels = _labels(r)
    assert any("addItem" in l for l in labels)
    assert any("process" in l for l in labels)

def test_swift_finds_function():
    r = extract_swift(FIXTURES / "sample.swift")
    assert any("createProcessor" in l for l in _labels(r))

def test_swift_finds_imports():
    r = extract_swift(FIXTURES / "sample.swift")
    assert "imports" in _relations(r)

def test_swift_no_dangling_edges():
    r = extract_swift(FIXTURES / "sample.swift")
    node_ids = {n["id"] for n in r["nodes"]}
    for e in r["edges"]:
        assert e["source"] in node_ids

def test_swift_finds_actor():
    r = extract_swift(FIXTURES / "sample.swift")
    assert any("CacheManager" in l for l in _labels(r))

def test_swift_finds_enum():
    r = extract_swift(FIXTURES / "sample.swift")
    assert any("NetworkError" in l for l in _labels(r))

def test_swift_finds_enum_methods():
    r = extract_swift(FIXTURES / "sample.swift")
    assert any("describe" in l for l in _labels(r))

def test_swift_finds_enum_cases():
    r = extract_swift(FIXTURES / "sample.swift")
    labels = _labels(r)
    assert any("timeout" in l for l in labels)
    assert any("connectionFailed" in l for l in labels)

def test_swift_enum_cases_have_case_of_edge():
    r = extract_swift(FIXTURES / "sample.swift")
    case_edges = [e for e in r["edges"] if e["relation"] == "case_of"]
    assert len(case_edges) >= 2

def test_swift_finds_deinit():
    r = extract_swift(FIXTURES / "sample.swift")
    assert any("deinit" in l for l in _labels(r))

def test_swift_finds_subscript():
    r = extract_swift(FIXTURES / "sample.swift")
    assert any("subscript" in l for l in _labels(r))

def test_swift_extension_methods_attach_to_type():
    r = extract_swift(FIXTURES / "sample.swift")
    node_by_id = {n["id"]: n["label"] for n in r["nodes"]}
    method_edges = [e for e in r["edges"] if e["relation"] == "method"]
    found = False
    for e in method_edges:
        src_label = node_by_id.get(e["source"], "")
        tgt_label = node_by_id.get(e["target"], "")
        if "Config" in src_label and "isValid" in tgt_label:
            found = True
            break
    assert found, "extension method isValid should attach to Config"

def test_swift_extension_does_not_duplicate_type_node():
    r = extract_swift(FIXTURES / "sample.swift")
    config_nodes = [n for n in r["nodes"] if n["label"] == "Config"]
    assert len(config_nodes) == 1, f"Config should appear once, got {len(config_nodes)}"

def test_swift_conformance_edge():
    r = extract_swift(FIXTURES / "sample.swift")
    inherits_edges = [e for e in r["edges"] if e["relation"] == "inherits"]
    node_by_id = {n["id"]: n["label"] for n in r["nodes"]}
    found = False
    for e in inherits_edges:
        src_label = node_by_id.get(e["source"], "")
        tgt_label = node_by_id.get(e["target"], "")
        if "DataProcessor" in src_label and "Processor" in tgt_label:
            found = True
            break
    assert found, "DataProcessor should have inherits edge to Processor"

def test_swift_extension_conformance_edge():
    r = extract_swift(FIXTURES / "sample.swift")
    inherits_edges = [e for e in r["edges"] if e["relation"] == "inherits"]
    node_by_id = {n["id"]: n["label"] for n in r["nodes"]}
    found = False
    for e in inherits_edges:
        src_label = node_by_id.get(e["source"], "")
        tgt_label = node_by_id.get(e["target"], "")
        if "DataProcessor" in src_label and "Loggable" in tgt_label:
            found = True
            break
    assert found, "extension should add conformance edge DataProcessor -> Loggable"

def test_swift_emits_calls():
    r = extract_swift(FIXTURES / "sample.swift")
    calls = _calls(r)
    assert any("process" in src and "validate" in tgt for src, tgt in calls)


# ── Elixir ────────────────────────────────────────────────────────────────────

from graphify.extract import extract_elixir

def test_elixir_finds_module():
    r = extract_elixir(FIXTURES / "sample.ex")
    assert "error" not in r
    labels = [n["label"] for n in r["nodes"]]
    assert any("MyApp.Accounts.User" in l for l in labels)

def test_elixir_finds_functions():
    r = extract_elixir(FIXTURES / "sample.ex")
    labels = [n["label"] for n in r["nodes"]]
    assert any("create" in l for l in labels)
    assert any("find" in l for l in labels)
    assert any("validate" in l for l in labels)

def test_elixir_finds_imports():
    r = extract_elixir(FIXTURES / "sample.ex")
    import_edges = [e for e in r["edges"] if e["relation"] == "imports"]
    assert len(import_edges) >= 2

def test_elixir_finds_calls():
    r = extract_elixir(FIXTURES / "sample.ex")
    calls = {(e["source"], e["target"]) for e in r["edges"] if e["relation"] == "calls"}
    labels = {n["id"]: n["label"] for n in r["nodes"]}
    assert any("create" in labels.get(src, "") and "validate" in labels.get(tgt, "") for src, tgt in calls)

def test_elixir_method_edges():
    r = extract_elixir(FIXTURES / "sample.ex")
    methods = [e for e in r["edges"] if e["relation"] == "method"]
    assert len(methods) >= 3


# ── Objective-C ──────────────────────────────────────────────────────────────
from graphify.extract import extract_objc


def test_objc_finds_interface():
    r = extract_objc(FIXTURES / "sample.m")
    labels = [n["label"] for n in r["nodes"]]
    assert "Animal" in labels


def test_objc_finds_subclass():
    r = extract_objc(FIXTURES / "sample.m")
    labels = [n["label"] for n in r["nodes"]]
    assert "Dog" in labels


def test_objc_finds_methods():
    r = extract_objc(FIXTURES / "sample.m")
    labels = [n["label"] for n in r["nodes"]]
    assert any("speak" in l or "fetch" in l or "initWithName" in l for l in labels)


def test_objc_finds_imports():
    r = extract_objc(FIXTURES / "sample.m")
    import_edges = [e for e in r["edges"] if e["relation"] == "imports"]
    assert len(import_edges) >= 1


def test_objc_inherits_edge():
    r = extract_objc(FIXTURES / "sample.m")
    inherits = [e for e in r["edges"] if e["relation"] == "inherits"]
    assert len(inherits) >= 1


def test_objc_no_dangling_edges():
    r = extract_objc(FIXTURES / "sample.m")
    node_ids = {n["id"] for n in r["nodes"]}
    for e in r["edges"]:
        assert e["source"] in node_ids, f"Dangling source: {e}"


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------

def test_go_receiver_methods_share_type_node():
    """Methods on the same receiver type must share one canonical type node."""
    r = extract_go(FIXTURES / "sample.go")
    server_nodes = [n for n in r["nodes"] if n["label"] == "Server"]
    # Both Start() and Stop() are on *Server — should produce exactly one Server node
    assert len(server_nodes) == 1

def test_go_receiver_uses_pkg_scope():
    """Type node id should be scoped to directory, not file stem."""
    r = extract_go(FIXTURES / "sample.go")
    server_nodes = [n for n in r["nodes"] if n["label"] == "Server"]
    assert server_nodes
    # Should NOT contain the file stem "sample" in the type node id
    assert "sample" not in server_nodes[0]["id"].split(":")[0]


# ---------------------------------------------------------------------------
# Julia
# ---------------------------------------------------------------------------

def test_julia_finds_module():
    r = extract_julia(FIXTURES / "sample.jl")
    labels = [n["label"] for n in r["nodes"]]
    assert "Geometry" in labels


def test_julia_finds_structs():
    r = extract_julia(FIXTURES / "sample.jl")
    labels = [n["label"] for n in r["nodes"]]
    assert "Point" in labels
    assert "Circle" in labels


def test_julia_finds_abstract_type():
    r = extract_julia(FIXTURES / "sample.jl")
    labels = [n["label"] for n in r["nodes"]]
    assert "Shape" in labels


def test_julia_finds_functions():
    r = extract_julia(FIXTURES / "sample.jl")
    labels = [n["label"] for n in r["nodes"]]
    assert any("area" in l for l in labels)
    assert any("distance" in l for l in labels)


def test_julia_finds_short_function():
    r = extract_julia(FIXTURES / "sample.jl")
    labels = [n["label"] for n in r["nodes"]]
    assert any("perimeter" in l for l in labels)


def test_julia_finds_imports():
    r = extract_julia(FIXTURES / "sample.jl")
    import_edges = [e for e in r["edges"] if e["relation"] == "imports"]
    assert len(import_edges) >= 1


def test_julia_finds_inherits():
    r = extract_julia(FIXTURES / "sample.jl")
    inherits = [e for e in r["edges"] if e["relation"] == "inherits"]
    assert len(inherits) >= 1


def test_julia_finds_calls():
    r = extract_julia(FIXTURES / "sample.jl")
    call_edges = [e for e in r["edges"] if e["relation"] == "calls"]
    assert len(call_edges) >= 1


def test_julia_no_dangling_edges():
    r = extract_julia(FIXTURES / "sample.jl")
    node_ids = {n["id"] for n in r["nodes"]}
    for e in r["edges"]:
        assert e["source"] in node_ids, f"Dangling source: {e}"


# ── ArkTS / .ets (HarmonyOS) ─────────────────────────────────────────────────

def test_ets_no_error():
    r = extract_ets(FIXTURES / "sample.ets")
    assert "error" not in r or r.get("nodes"), f"Unexpected failure: {r}"


def test_ets_struct_parsed_as_class():
    """struct should be preprocessed → class so AST picks it up."""
    r = extract_ets(FIXTURES / "sample.ets")
    labels = _labels(r)
    assert any("EnvCheckPage" in l for l in labels), f"Missing EnvCheckPage struct: {labels}"
    assert any("LegacyPage" in l for l in labels), f"Missing LegacyPage struct: {labels}"


def test_ets_finds_regular_class():
    """Plain `class` still works alongside struct."""
    r = extract_ets(FIXTURES / "sample.ets")
    assert any("CheckBean" in l for l in _labels(r))


def test_ets_finds_methods():
    r = extract_ets(FIXTURES / "sample.ets")
    labels = _labels(r)
    assert any("build" in l for l in labels)
    assert any("aboutToAppear" in l for l in labels)
    assert any("startCheck" in l for l in labels)


def test_ets_finds_imports():
    r = extract_ets(FIXTURES / "sample.ets")
    rels = _relations(r)
    assert "imports" in rels or "imports_from" in rels, f"No import relation in {rels}"


def test_ets_component_decorator_is_recognized():
    """@Entry / @ComponentV2 / @Component should become arkts_decorator nodes."""
    r = extract_ets(FIXTURES / "sample.ets")
    deco_nodes = [n for n in r["nodes"] if n.get("node_type") == "arkts_decorator"]
    deco_labels = {n["label"] for n in deco_nodes}
    assert "@Entry" in deco_labels, f"Expected @Entry, got {deco_labels}"
    assert "@ComponentV2" in deco_labels, f"Expected @ComponentV2, got {deco_labels}"
    assert "@Component" in deco_labels, f"Expected @Component, got {deco_labels}"


def test_ets_decorator_edges_target_struct():
    r = extract_ets(FIXTURES / "sample.ets")
    deco_edges = [e for e in r["edges"] if e["relation"] == "decorates"]
    assert len(deco_edges) >= 2, f"Expected ≥2 decorates edges, got {deco_edges}"


def test_ets_state_decorators_create_state_nodes():
    """@Local / @State / @Prop / @Link / @Trace etc. → arkts_state nodes."""
    r = extract_ets(FIXTURES / "sample.ets")
    state_nodes = [n for n in r["nodes"] if n.get("node_type") == "arkts_state"]
    state_labels = {n["label"] for n in state_nodes}
    # V2 decorators
    assert any("@Local" in l for l in state_labels), f"No @Local in {state_labels}"
    assert any("@Trace" in l for l in state_labels), f"No @Trace in {state_labels}"
    # V1 decorators
    assert any("@State" in l for l in state_labels), f"No @State in {state_labels}"
    assert any("@Prop" in l for l in state_labels), f"No @Prop in {state_labels}"
    assert any("@Link" in l for l in state_labels), f"No @Link in {state_labels}"


def test_ets_no_dangling_edges():
    """Source endpoints must always exist as nodes. Import targets may legitimately
    point at external modules that are not nodes until cross-file resolution."""
    r = extract_ets(FIXTURES / "sample.ets")
    node_ids = {n["id"] for n in r["nodes"]}
    for e in r["edges"]:
        assert e["source"] in node_ids, f"Dangling source: {e}"
        if e["relation"] in ("imports_from", "imports"):
            continue  # external-module targets are OK
        assert e["target"] in node_ids, f"Dangling target: {e}"


def test_ets_preserves_line_numbers():
    """struct→class preprocessing must keep byte offsets so line numbers match."""
    r = extract_ets(FIXTURES / "sample.ets")
    for n in r["nodes"]:
        if n["label"] == "EnvCheckPage":
            assert n["source_location"] == "L29", f"Line mismatch: {n}"
            break
    else:
        pytest.fail("EnvCheckPage node not found")


# ── Enriched ArkTS semantics (V1+V2 full coverage) ───────────────────────────

def test_ets_component_struct_marked_as_component():
    """@Component / @ComponentV2 struct nodes should be tagged arkts_component."""
    r = extract_ets(FIXTURES / "sample.ets")
    comps = {n["label"] for n in r["nodes"] if n.get("node_type") == "arkts_component"}
    assert "EnvCheckPage" in comps, f"EnvCheckPage not marked as component: {comps}"
    assert "LegacyPage" in comps, f"LegacyPage not marked as component: {comps}"


def test_ets_observed_v2_class_marked():
    """@ObservedV2 class should be tagged arkts_observed_v2."""
    r = extract_ets(FIXTURES / "sample.ets")
    observed = {n["label"] for n in r["nodes"] if n.get("node_type") == "arkts_observed_v2"}
    assert "CheckBean" in observed, f"CheckBean not marked as observed_v2: {observed}"


def test_ets_lifecycle_methods_tagged():
    """Lifecycle methods should be tagged arkts_lifecycle and linked via has_lifecycle."""
    r = extract_ets(FIXTURES / "sample.ets")
    lifecycle_labels = {n["label"] for n in r["nodes"] if n.get("node_type") == "arkts_lifecycle"}
    assert any("aboutToAppear" in l for l in lifecycle_labels)
    assert any("onPageShow" in l for l in lifecycle_labels)
    lifecycle_edges = [e for e in r["edges"] if e["relation"] == "has_lifecycle"]
    assert len(lifecycle_edges) >= 2, f"Expected ≥2 has_lifecycle edges, got {lifecycle_edges}"


def test_ets_observes_edges_for_traced_fields():
    """@Trace fields inside @ObservedV2 class → observes edge from class."""
    r = extract_ets(FIXTURES / "sample.ets")
    obs_edges = [e for e in r["edges"] if e["relation"] == "observes"]
    assert len(obs_edges) >= 2, f"Expected ≥2 observes edges, got {obs_edges}"


def test_ets_watch_binds_to_target_method():
    """@Watch('onCountChange') should create a watches edge to the onCountChange method."""
    r = extract_ets(FIXTURES / "sample.ets")
    watch_edges = [e for e in r["edges"] if e["relation"] == "watches"]
    assert len(watch_edges) >= 1, f"Expected ≥1 watches edge, got {watch_edges}"
    watch_nodes = [n for n in r["nodes"] if n.get("node_type") == "arkts_watch"]
    assert any("onCountChange" in n["label"] for n in watch_nodes)


def test_ets_monitor_targets_captured():
    """@Monitor('checkState', 'model.titleName') → two monitor_target nodes + monitors edges."""
    r = extract_ets(FIXTURES / "sample.ets")
    monitor_nodes = [n for n in r["nodes"] if n.get("node_type") == "arkts_monitor_target"]
    monitor_labels = {n["label"] for n in monitor_nodes}
    assert any("checkState" in l for l in monitor_labels)
    assert any("model.titleName" in l for l in monitor_labels)
    monitors_edges = [e for e in r["edges"] if e["relation"] == "monitors"]
    assert len(monitors_edges) >= 2


def test_ets_provide_consume_share_key_node():
    """@Provider('sharedKey') + @Consume('sharedKey') should connect via same key node."""
    r = extract_ets(FIXTURES / "sample.ets")
    provides = [e for e in r["edges"] if e["relation"] == "provides"]
    consumes = [e for e in r["edges"] if e["relation"] == "consumes"]
    assert len(provides) >= 1, f"No provides edges: {provides}"
    assert len(consumes) >= 1, f"No consumes edges: {consumes}"
    # Same target key node
    assert {e["target"] for e in provides} == {e["target"] for e in consumes}


def test_ets_storage_bindings_emit_key_nodes():
    """@StorageLink('globalUser') → arkts_app_storage_key node, storage_binds edge."""
    r = extract_ets(FIXTURES / "sample.ets")
    app_keys = {n["label"] for n in r["nodes"] if n.get("node_type") == "arkts_app_storage_key"}
    local_keys = {n["label"] for n in r["nodes"] if n.get("node_type") == "arkts_local_storage_key"}
    assert any("globalUser" in l for l in app_keys), f"globalUser not found: {app_keys}"
    assert any("sessionId" in l for l in local_keys), f"sessionId not found: {local_keys}"


def test_ets_ui_composition_from_build():
    """build() body should emit uses_component edges to child components."""
    r = extract_ets(FIXTURES / "sample.ets")
    ui_edges = [e for e in r["edges"] if e["relation"] == "uses_component"]
    used_labels = set()
    node_by_id = {n["id"]: n for n in r["nodes"]}
    for e in ui_edges:
        if e["target"] in node_by_id:
            used_labels.add(node_by_id[e["target"]]["label"])
    # EnvCheckPage uses at least: NavDestination, Column, TitleBar, Scroll, List, ForEach, ListItem, Text, Button
    expected = {"NavDestination", "Column", "TitleBar", "Scroll", "List", "ForEach", "ListItem", "Text", "Button"}
    missing = expected - used_labels
    assert not missing, f"Missing UI components: {missing}; got {used_labels}"


def test_ets_resources_extracted():
    """$r('app.color.xxx') / $r('app.string.xxx') → arkts_resource nodes."""
    r = extract_ets(FIXTURES / "sample.ets")
    resources = [n for n in r["nodes"] if n.get("node_type") == "arkts_resource"]
    resource_keys = {n["label"] for n in resources}
    assert any("app.media.icon" in l for l in resource_keys)
    assert any("app.string.submit" in l for l in resource_keys)
    assert any("app.color.color_text" in l for l in resource_keys)
    ref_edges = [e for e in r["edges"] if e["relation"] == "references_resource"]
    assert len(ref_edges) >= 2


def test_ets_all_v1_state_decorators_recognized():
    """Check @State / @Prop / @Link / @Provide / @Consume / @Watch / @Observed / @ObjectLink."""
    r = extract_ets(FIXTURES / "sample.ets")
    state_labels = {n["label"] for n in r["nodes"] if n.get("node_type") == "arkts_state"}
    # We have @State oldFashionedState, @Prop title, @Link shared in the fixture
    v1_seen = {"State", "Prop", "Link"}
    for needed in v1_seen:
        assert any(f"@{needed}" in l for l in state_labels), f"Missing @{needed} state node"


def test_ets_all_v2_state_decorators_recognized():
    """Check @Local / @Param / @Event / @Trace / @Computed via state nodes."""
    r = extract_ets(FIXTURES / "sample.ets")
    state_labels = {n["label"] for n in r["nodes"] if n.get("node_type") == "arkts_state"}
    for needed in ("Local", "Param", "Event", "Trace", "Computed"):
        assert any(f"@{needed}" in l for l in state_labels), f"Missing @{needed} state node: {state_labels}"
