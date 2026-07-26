"""Pruebas sintéticas de la exportación PyVis local y sanitizada."""

from __future__ import annotations

import asyncio
import re
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest

from app.core.exceptions import GraphError
from app.database.models.hpn import (
    HpnMatrixStatus,
    HpnNodeType,
    HpnRelationType,
    HpnReviewStatus,
)
from app.schemas.hpn_graph import (
    GraphEdge,
    GraphMatrix,
    GraphNode,
    GraphSummary,
    GraphWarning,
    HpnGraphProjection,
    SourceStatusSummary,
)
from app.visualization import hpn_pyvis_renderer as renderer_module
from app.visualization.hpn_pyvis_renderer import (
    HpnPyvisRenderer,
    build_visual_graph,
)


def _uuid(value: int) -> UUID:
    return UUID(int=value)


def _node(
    value: int,
    node_type: HpnNodeType,
    *,
    label: str | None = None,
    review_status: HpnReviewStatus = HpnReviewStatus.REVIEWED,
    valid: int = 0,
    stale: int = 0,
    unavailable: int = 0,
) -> GraphNode:
    total = valid + stale + unavailable
    flags: list[str] = []
    if review_status == HpnReviewStatus.DRAFT:
        flags.append("GRAPH_REVIEW_DRAFT")
    if review_status == HpnReviewStatus.REJECTED:
        flags.append("GRAPH_REVIEW_REJECTED")
    if stale:
        flags.append("GRAPH_SOURCE_STALE")
    if unavailable:
        flags.append("GRAPH_SOURCE_UNAVAILABLE")
    return GraphNode(
        id=_uuid(value),
        type=node_type,
        label=label or f"Nodo {value}",
        review_status=review_status,
        display_order=value,
        source_summary=SourceStatusSummary(
            total=total,
            valid=valid,
            stale=stale,
            unavailable=unavailable,
            has_warnings=bool(stale or unavailable),
        ),
        warning_flags=tuple(flags),  # type: ignore[arg-type]
    )


def _edge(
    value: int,
    source: GraphNode,
    target: GraphNode,
    relation_type: HpnRelationType,
    *,
    review_status: HpnReviewStatus = HpnReviewStatus.REVIEWED,
) -> GraphEdge:
    warning_flags: tuple[str, ...] = ()
    if review_status == HpnReviewStatus.DRAFT:
        warning_flags = ("GRAPH_REVIEW_DRAFT",)
    elif review_status == HpnReviewStatus.REJECTED:
        warning_flags = ("GRAPH_REVIEW_REJECTED",)
    return GraphEdge(
        id=_uuid(value),
        source=source.id,
        target=target.id,
        relation_type=relation_type,
        label=relation_type.value,
        review_status=review_status,
        warning_flags=warning_flags,  # type: ignore[arg-type]
    )


def _projection(
    *,
    nodes: tuple[GraphNode, ...] = (),
    edges: tuple[GraphEdge, ...] = (),
    archived: bool = False,
    warnings: tuple[GraphWarning, ...] = (),
) -> HpnGraphProjection:
    status = HpnMatrixStatus.ARCHIVED if archived else HpnMatrixStatus.DRAFT
    return HpnGraphProjection(
        matrix=GraphMatrix(
            id=_uuid(1),
            status=status,
            label="Matriz privada",
            read_only=archived,
            valid_for_review=False,
        ),
        nodes=nodes,
        edges=edges,
        warnings=warnings,
        summary=GraphSummary(
            node_count=len(nodes),
            edge_count=len(edges),
            isolated_node_count=len(nodes) if not edges else 0,
            disconnected_components=0 if not nodes else 1,
            has_directed_cycles=False,
            structural_warning_count=sum(
                warning.code
                in {
                    "GRAPH_EMPTY",
                    "GRAPH_DISCONNECTED_COMPONENTS",
                    "GRAPH_DIRECTED_CYCLE_DETECTED",
                }
                for warning in warnings
            ),
        ),
    )


def _render(projection: HpnGraphProjection) -> str:
    return asyncio.run(HpnPyvisRenderer().render(projection)).html


def test_visual_dto_aliases_are_minimal_deterministic_and_uuid_free() -> None:
    fact = _node(10, HpnNodeType.FACT)
    evidence = _node(20, HpnNodeType.EVIDENCE, valid=1)
    edge = _edge(30, evidence, fact, HpnRelationType.EVIDENCE_SUPPORTS_FACT)
    projection = _projection(nodes=(fact, evidence), edges=(edge,))
    first = build_visual_graph(projection)
    second = build_visual_graph(projection)
    assert first == second
    assert [node.alias for node in first.nodes] == ["n-0001", "n-0002"]
    assert [item.alias for item in first.edges] == ["e-0001"]
    serialized = repr(first)
    assert "Matriz privada" not in serialized
    assert str(projection.matrix.id) not in serialized
    assert all(str(node.id) not in serialized for node in projection.nodes)
    assert all(str(item.id) not in serialized for item in projection.edges)


def test_renderer_supports_three_node_types_four_relations_and_multiedges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(renderer_module.secrets, "token_urlsafe", lambda _: "fixednonce")
    fact = _node(10, HpnNodeType.FACT)
    evidence = _node(20, HpnNodeType.EVIDENCE, stale=1)
    norm = _node(30, HpnNodeType.NORM, unavailable=1)
    edges = (
        _edge(40, evidence, fact, HpnRelationType.EVIDENCE_SUPPORTS_FACT),
        _edge(41, evidence, fact, HpnRelationType.EVIDENCE_CONTRADICTS_FACT),
        _edge(42, norm, fact, HpnRelationType.NORM_APPLIES_TO_FACT),
        _edge(43, norm, fact, HpnRelationType.NORM_LIMITS_FACT),
    )
    projection = _projection(nodes=(fact, evidence, norm), edges=edges)
    first = _render(projection)
    second = _render(projection)
    assert first == second
    for alias in ("n-0001", "n-0002", "n-0003", "e-0001", "e-0004"):
        assert alias in first
    for private_id in (projection.matrix.id, *(node.id for node in projection.nodes)):
        assert str(private_id) not in first
    assert first.count('"from": "n-0002"') == 2
    assert '"type": "curvedCW"' in first
    assert '"type": "curvedCCW"' in first


@pytest.mark.parametrize(
    "malicious",
    [
        '<script>globalThis.compromised=true</script>',
        '</script><script>globalThis.compromised=true</script>',
        '<img src=x onerror="globalThis.compromised=true">',
        '<svg onload="globalThis.compromised=true"></svg>',
        '<iframe srcdoc="<script>globalThis.compromised=true</script>"></iframe>',
        '<a href="javascript:globalThis.compromised=true">enlace</a>',
        '" onmouseover="globalThis.compromised=true',
        "' autofocus onfocus='globalThis.compromised=true",
        "${globalThis.compromised=true}",
        "&lt;script&gt;globalThis.compromised=true&lt;/script&gt;",
        "texto con ' comillas & < > y ` backtick",
        "acción jurídica, español y eñe",
        "control\u0000\u0007visible",
    ],
)
def test_renderer_serializes_untrusted_labels_as_text(malicious: str) -> None:
    node = _node(10, HpnNodeType.FACT, label=malicious)
    rendered = _render(_projection(nodes=(node,)))
    assert "globalThis.compromised=true</script>" not in rendered
    assert "<img src=x" not in rendered
    assert "\x00" not in rendered
    assert "\x07" not in rendered
    assert str(node.id) not in rendered


def test_renderer_tooltip_limit_and_closed_styles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(renderer_module.settings, "graph_max_tooltip_length", 80)
    node = _node(
        10,
        HpnNodeType.EVIDENCE,
        label="Etiqueta extensa " * 20,
        review_status=HpnReviewStatus.REJECTED,
        stale=1,
        unavailable=1,
    )
    visual = build_visual_graph(_projection(nodes=(node,)))
    assert len(renderer_module._node_tooltip(visual.nodes[0])) <= 80
    assert visual.nodes[0].source_status.category == "mixed"
    rendered = _render(_projection(nodes=(node,)))
    assert '"shape": "ellipse"' in rendered
    assert '"dashes": true' in rendered
    assert '"group": "evidence-rejected-mixed"' in rendered


def test_tooltips_are_text_only_in_the_pinned_vis_network_bundle() -> None:
    label = '<img src=x onerror=alert(1)> &lt;script&gt; " `'
    node = _node(10, HpnNodeType.EVIDENCE, label=label, valid=1)
    visual = build_visual_graph(_projection(nodes=(node,)))
    tooltip = renderer_module._node_tooltip(visual.nodes[0])
    assert "fuentes: total 1" in tooltip
    assert "<img" in tooltip
    rendered = _render(_projection(nodes=(node,)))
    assert "this.frame.innerText=t" in rendered
    assert "\\u003cimg" in rendered
    assert "<img src=x" not in rendered


def test_renderer_is_offline_nonce_protected_and_uses_fixed_options() -> None:
    node = _node(10, HpnNodeType.NORM)
    result = asyncio.run(HpnPyvisRenderer().render(_projection(nodes=(node,))))
    lowered = result.html.lower()
    assert result.html.count(f'nonce="{result.nonce}"') == 3
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "//cdn" not in lowered
    assert not any(item in lowered for item in ("cdnjs", "unpkg", "jsdelivr"))
    assert "eval(" not in lowered
    assert "new function" not in lowered
    assert "document.write" not in lowered
    assert "localstorage" not in lowered
    assert "sessionstorage" not in lowered
    assert "window.parent" not in lowered
    assert "window.opener" not in lowered
    assert "window.top" not in lowered
    assert "postmessage" not in lowered
    assert "javascript:" not in lowered
    assert "sourcemappingurl" not in lowered
    assert "<script>" not in lowered
    assert "\\u0068ttps://" not in result.html
    assert '"direction": "lr"' in lowered
    assert '"physics": {"enabled": false}' in lowered
    assert "visualización estructural de apoyo" in lowered
    assert "requiere revisión profesional" in lowered


def test_every_script_and_style_has_the_response_nonce_and_nonce_changes() -> None:
    projection = _projection(nodes=(_node(10, HpnNodeType.FACT),))
    first = asyncio.run(HpnPyvisRenderer().render(projection))
    second = asyncio.run(HpnPyvisRenderer().render(projection))
    assert first.nonce != second.nonce
    for result in (first, second):
        tags = re.findall(r"<(?:script|style)\b([^>]*)>", result.html, re.IGNORECASE)
        assert len(tags) == 3
        assert all(f'nonce="{result.nonce}"' in attributes for attributes in tags)
        assert result.html_bytes == len(result.html.encode("utf-8"))
        assert result.html_bytes > len(result.html)


def test_structure_is_deterministic_after_normalizing_the_nonce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection(nodes=(_node(10, HpnNodeType.FACT),))
    nonces = iter(("a" * 43, "b" * 43))
    monkeypatch.setattr(renderer_module.secrets, "token_urlsafe", lambda _: next(nonces))
    first = asyncio.run(HpnPyvisRenderer().render(projection))
    second = asyncio.run(HpnPyvisRenderer().render(projection))

    def normalized(result: renderer_module.RenderedGraphHtml) -> str:
        return result.html.replace(result.nonce, "<nonce>")

    assert normalized(first) == normalized(second)
    assert first.html_bytes == second.html_bytes


def test_empty_and_archived_graphs_are_safe_and_do_not_initialize_vis() -> None:
    empty = _render(
        _projection(
            archived=True,
            warnings=(
                GraphWarning(code="GRAPH_EMPTY", entity_type="graph", severity="info"),
            ),
        )
    )
    assert "0 nodos y 0 aristas" in empty
    assert "solo lectura" in empty
    assert "new vis.Network" not in empty
    assert "vis-network.min" not in empty


def test_warnings_use_fixed_text_without_entities() -> None:
    node = _node(
        10,
        HpnNodeType.EVIDENCE,
        review_status=HpnReviewStatus.DRAFT,
        stale=1,
        unavailable=1,
    )
    warnings = tuple(
        GraphWarning(code=code, entity_type="node", entity_id=node.id, severity="warning")
        for code in (
            "GRAPH_REVIEW_DRAFT",
            "GRAPH_SOURCE_STALE",
            "GRAPH_SOURCE_UNAVAILABLE",
        )
    )
    rendered = _render(_projection(nodes=(node,), warnings=warnings))
    assert "elementos en borrador" in rendered
    assert "fuente obsoletas" in rendered
    assert "fuente no disponibles" in rendered
    assert str(node.id) not in rendered


def test_relation_review_cycles_and_components_use_only_fixed_warnings() -> None:
    fact = _node(10, HpnNodeType.FACT)
    evidence = _node(20, HpnNodeType.EVIDENCE)
    draft_edge = _edge(
        30,
        evidence,
        fact,
        HpnRelationType.EVIDENCE_SUPPORTS_FACT,
        review_status=HpnReviewStatus.DRAFT,
    )
    rejected_edge = _edge(
        31,
        evidence,
        fact,
        HpnRelationType.EVIDENCE_CONTRADICTS_FACT,
        review_status=HpnReviewStatus.REJECTED,
    )
    warnings = (
        GraphWarning(
            code="GRAPH_REVIEW_DRAFT",
            entity_type="edge",
            entity_id=draft_edge.id,
            severity="warning",
        ),
        GraphWarning(
            code="GRAPH_REVIEW_REJECTED",
            entity_type="edge",
            entity_id=rejected_edge.id,
            severity="warning",
        ),
        GraphWarning(
            code="GRAPH_DISCONNECTED_COMPONENTS",
            entity_type="graph",
            severity="warning",
        ),
        GraphWarning(
            code="GRAPH_DIRECTED_CYCLE_DETECTED",
            entity_type="graph",
            severity="warning",
        ),
    )
    rendered = _render(
        _projection(
            nodes=(fact, evidence),
            edges=(draft_edge, rejected_edge),
            warnings=warnings,
        )
    )
    assert "elementos en borrador" in rendered
    assert "elementos rechazados" in rendered
    assert "componentes estructurales desconectados" in rendered
    assert "ciclo estructural dirigido" in rendered
    assert str(draft_edge.id) not in rendered
    assert str(rejected_edge.id) not in rendered


def test_renderer_rejects_visual_and_final_html_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(renderer_module.settings, "graph_max_html_bytes", 100)
    with pytest.raises(GraphError, match="GRAPH_TOO_LARGE"):
        _render(_projection(nodes=(_node(10, HpnNodeType.FACT),)))
    monkeypatch.setattr(renderer_module.settings, "graph_max_html_bytes", 1000)
    with pytest.raises(GraphError, match="GRAPH_TOO_LARGE"):
        _render(_projection())


def test_missing_pyvis_and_internal_import_failures_are_distinguished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_pyvis(_: str) -> object:
        exc = ModuleNotFoundError("pyvis missing")
        exc.name = "pyvis"
        raise exc

    monkeypatch.setattr(renderer_module.importlib, "import_module", missing_pyvis)
    with pytest.raises(GraphError, match="GRAPH_DEPENDENCY_NOT_AVAILABLE"):
        _render(_projection())

    def missing_internal(_: str) -> object:
        exc = ModuleNotFoundError("internal missing")
        exc.name = "jinja2_internal"
        raise exc

    monkeypatch.setattr(renderer_module.importlib, "import_module", missing_internal)
    with pytest.raises(GraphError, match="GRAPH_RENDER_FAILED"):
        _render(_projection())


def test_unexpected_render_failure_is_safe_and_semaphore_is_released(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fail_once(*_: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("private render detail")
        raise GraphError("GRAPH_TOO_LARGE")

    monkeypatch.setattr(renderer_module, "_render_visual_graph", fail_once)
    with pytest.raises(GraphError, match="GRAPH_RENDER_FAILED"):
        _render(_projection())
    with pytest.raises(GraphError, match="GRAPH_TOO_LARGE"):
        _render(_projection())
    assert calls == 2


def test_render_uses_worker_thread_and_leaves_no_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = tuple(tmp_path.iterdir())
    observed: dict[str, int] = {}
    original = renderer_module._render_visual_graph

    def observe(*args: object):
        observed["thread"] = threading.get_ident()
        return original(*args)  # type: ignore[arg-type]

    import threading

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(renderer_module, "_render_visual_graph", observe)
    caller_thread = threading.get_ident()
    _render(_projection(nodes=(_node(10, HpnNodeType.FACT),)))
    assert observed["thread"] != caller_thread
    assert tuple(tmp_path.iterdir()) == before


def test_renderer_redacts_actual_ids_and_remote_references_from_labels() -> None:
    node = _node(
        10,
        HpnNodeType.FACT,
        label=f"ID {_uuid(10)} https://example.invalid cdnjs",
    )
    rendered = _render(_projection(nodes=(node,)))
    assert str(node.id) not in rendered
    assert "example.invalid" not in rendered
    assert "cdnjs" not in rendered.lower()
    assert "identificador omitido" in rendered


def test_script_closing_entities_unicode_separators_and_invisible_controls_are_safe() -> None:
    payload = (
        "</script><script>alert(1)</script><!-- --> "
        "&lt;svg onload=alert(1)&gt; ${alert(1)} "
        "\u2028\u2029\u202e\u200b\u0085"
    )
    projection = _projection(nodes=(_node(10, HpnNodeType.FACT, label=payload),))
    visual_label = build_visual_graph(projection).nodes[0].label
    rendered = _render(projection)
    assert "</script><script" not in rendered.lower()
    assert "<svg onload" not in rendered.lower()
    assert "<!--" not in rendered
    assert "-->" not in rendered
    assert "\u2028" not in rendered
    assert "\u2029" not in rendered
    assert "\u202e" not in visual_label
    assert "\u200b" not in visual_label
    assert "\u0085" not in visual_label


def test_aliases_remain_zero_padded_beyond_nine_and_ninety_nine() -> None:
    nodes = tuple(_node(index, HpnNodeType.FACT) for index in range(1, 101))
    visual = build_visual_graph(_projection(nodes=nodes))
    assert visual.nodes[9].alias == "n-0010"
    assert visual.nodes[99].alias == "n-0100"
    assert len({node.alias for node in visual.nodes}) == 100


@pytest.mark.parametrize(
    "css",
    [
        '.x{background:url("https://remote.invalid/a.png")}',
        ".x{background:url(HTTP : //remote.invalid/a.png)}",
        '.x{background:url("&#104;ttps&#58;//remote.invalid/a.png")}',
        r'.x{background:url("\u0068ttps:\/\/remote.invalid/a.png")}',
        '.x{background:url("//cdn.invalid/a.png")}',
        '.x{background:url("javascript:alert(1)")}',
        '.x{background:url("data:text/html,unsafe")}',
        '@import "remote.css";',
        '@font-face{font-family:x;src:url("data:font/woff;base64,AA")}',
        "/*# sourceMappingURL=remote.css.map */",
    ],
)
def test_offline_css_rejects_remote_obfuscated_and_unsafe_resources(css: str) -> None:
    with pytest.raises(GraphError, match="GRAPH_RENDER_FAILED"):
        renderer_module._validate_offline_css(css)


def test_offline_css_allows_only_controlled_inline_png_data() -> None:
    renderer_module._validate_offline_css(
        '.x{background-image:url("data:image/png;base64,AAAA")}'
    )


@pytest.mark.parametrize(
    "payload",
    [
        '"https://remote.invalid"',
        '"H T T P S : //remote.invalid"',
        r'"\u0068ttps:\/\/remote.invalid"',
        '"&#104;ttps&#58;//remote.invalid"',
        '"//cdn.invalid/resource"',
        '"javascript:alert(1)"',
        '"file:C:/private"',
        '"wss://remote.invalid"',
        "//# sourceMappingURL=remote.map",
        'document.createElement("style")',
        "sheet.insertRule('x')",
    ],
)
def test_offline_javascript_rejects_unsafe_variants(payload: str) -> None:
    _, package_dir = renderer_module._load_pyvis()
    _, javascript = renderer_module._load_offline_assets(package_dir)
    with pytest.raises(GraphError, match="GRAPH_RENDER_FAILED"):
        renderer_module._validate_offline_javascript(javascript + payload)


def test_real_local_assets_are_sanitized_and_contain_no_remote_fallback() -> None:
    _, package_dir = renderer_module._load_pyvis()
    css, javascript = renderer_module._load_offline_assets(package_dir)
    assert "sourceMappingURL" not in javascript
    assert "javascript:" not in javascript
    assert "<script" not in javascript
    assert "https://" not in javascript
    assert "http://" not in javascript
    assert "@import" not in css
    assert "@font-face" not in css
    assert re.search(r"url\([^)]*https?", css, re.IGNORECASE) is None


def test_offline_assets_reject_symlink_escape_when_supported(tmp_path: Path) -> None:
    package = tmp_path / "pyvis"
    asset_dir = package / "lib" / "vis-9.1.2"
    external = tmp_path / "external.css"
    asset_dir.mkdir(parents=True)
    external.write_text(".external{}", encoding="utf-8")
    try:
        (asset_dir / "vis-network.css").symlink_to(external)
    except OSError:
        pytest.skip("El sistema no permite crear symlinks para esta prueba")
    with pytest.raises(GraphError, match="GRAPH_RENDER_FAILED"):
        renderer_module._load_offline_assets(package)


def test_importing_application_and_router_does_not_import_pyvis() -> None:
    script = """
import sys
class BlockPyvis:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pyvis' or fullname.startswith('pyvis.'):
            raise AssertionError('PYVIS_IMPORTED_EAGERLY')
        return None
sys.meta_path.insert(0, BlockPyvis())
import app.main
import app.api.routes.hpn_graph
assert not any(name == 'pyvis' or name.startswith('pyvis.') for name in sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def test_renderer_is_safe_across_distinct_event_loops() -> None:
    projection = _projection(nodes=(_node(10, HpnNodeType.FACT),))
    first = asyncio.run(HpnPyvisRenderer().render(projection))
    second = asyncio.run(HpnPyvisRenderer().render(projection))
    assert first.html_bytes == second.html_bytes


def test_template_never_marks_hpn_text_safe() -> None:
    template = (
        Path(renderer_module.__file__).resolve().parents[1]
        / "templates"
        / "hpn_graph.html.j2"
    ).read_text(encoding="utf-8")
    assert "|safe" not in template
    assert "Markup" not in template
    assert re.search(r"\son\w+\s*=", template, flags=re.IGNORECASE) is None
