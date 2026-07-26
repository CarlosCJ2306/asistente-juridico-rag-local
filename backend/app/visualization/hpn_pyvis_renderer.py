"""Exportación PyVis en memoria de una proyección HPN mínima y sanitizada."""

from __future__ import annotations

import html
import importlib
import json
import re
import secrets
import threading
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, TypeAlias, cast

import anyio
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.core.config import settings
from app.core.exceptions import GraphError
from app.schemas.hpn_graph import HpnGraphProjection


VisualNodeType: TypeAlias = Literal["fact", "evidence", "norm"]
VisualReviewStatus: TypeAlias = Literal["draft", "reviewed", "rejected"]
VisualSourceCategory: TypeAlias = Literal[
    "valid", "stale", "unavailable", "mixed", "none"
]
VisualRelationType: TypeAlias = Literal[
    "evidence_supports_fact",
    "evidence_contradicts_fact",
    "norm_applies_to_fact",
    "norm_limits_fact",
]


@dataclass(frozen=True, slots=True)
class VisualNode:
    """Nodo visual sin identificadores HPN ni contenido documental."""

    alias: str
    type: VisualNodeType
    label: str
    review_status: VisualReviewStatus
    source_status: VisualSourceStatus
    warning_flags: tuple[str, ...]
    visual_group: str


@dataclass(frozen=True, slots=True)
class VisualSourceStatus:
    """Categoría visual y conteos mínimos de fuentes, sin referencias."""

    category: VisualSourceCategory
    total: int
    valid: int
    stale: int
    unavailable: int


@dataclass(frozen=True, slots=True)
class VisualEdge:
    """Arista visual trazable solo mediante aliases efímeros."""

    alias: str
    source_alias: str
    target_alias: str
    relation_type: VisualRelationType
    label: str
    review_status: VisualReviewStatus
    warning_flags: tuple[str, ...]
    visual_style: str


@dataclass(frozen=True, slots=True)
class VisualSummary:
    node_count: int
    edge_count: int
    disconnected_components: int
    has_directed_cycles: bool


@dataclass(frozen=True, slots=True)
class VisualGraph:
    """DTO visual inmutable y mínimo que recibe el renderer."""

    nodes: tuple[VisualNode, ...]
    edges: tuple[VisualEdge, ...]
    summary: VisualSummary
    warnings: tuple[str, ...]
    read_only: bool
    requires_professional_review: Literal[True] = True


@dataclass(frozen=True, slots=True)
class RenderedGraphHtml:
    html: str
    nonce: str
    html_bytes: int


_NODE_STYLES = MappingProxyType(
    {
        "fact": {"shape": "box", "background": "#dbeafe"},
        "evidence": {"shape": "ellipse", "background": "#dcfce7"},
        "norm": {"shape": "diamond", "background": "#fef3c7"},
    }
)
_REVIEW_STYLES = MappingProxyType(
    {
        "draft": {"border": "#64748b", "dashes": True},
        "reviewed": {"border": "#334155", "dashes": False},
        "rejected": {"border": "#b91c1c", "dashes": True},
    }
)
_SOURCE_BORDERS = MappingProxyType(
    {
        "valid": "#15803d",
        "stale": "#b45309",
        "unavailable": "#b91c1c",
        "mixed": "#7c3aed",
        "none": "#475569",
    }
)
_EDGE_STYLES = MappingProxyType(
    {
        "evidence_supports_fact": {"color": "#2563eb", "dashes": False},
        "evidence_contradicts_fact": {"color": "#dc2626", "dashes": True},
        "norm_applies_to_fact": {"color": "#7c3aed", "dashes": False},
        "norm_limits_fact": {"color": "#d97706", "dashes": True},
    }
)
_WARNING_MESSAGES = MappingProxyType(
    {
        "GRAPH_EMPTY": "La matriz no contiene nodos visibles.",
        "GRAPH_DISCONNECTED_COMPONENTS": (
            "La red contiene componentes estructurales desconectados."
        ),
        "GRAPH_DIRECTED_CYCLE_DETECTED": (
            "La red contiene al menos un ciclo estructural dirigido."
        ),
        "GRAPH_MATRIX_ARCHIVED": "La matriz está archivada y es de solo lectura.",
        "GRAPH_REVIEW_DRAFT": "La red contiene elementos en borrador.",
        "GRAPH_REVIEW_REJECTED": "La red contiene elementos rechazados.",
        "GRAPH_SOURCE_STALE": "La red contiene referencias de fuente obsoletas.",
        "GRAPH_SOURCE_UNAVAILABLE": (
            "La red contiene referencias de fuente no disponibles."
        ),
    }
)
_VIS_OPTIONS = MappingProxyType(
    {
        "autoResize": True,
        "configure": {"enabled": False},
        "edges": {
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.8}},
            "font": {"align": "middle", "size": 12},
            "smooth": {"enabled": True, "type": "cubicBezier"},
        },
        "interaction": {
            "dragNodes": False,
            "dragView": True,
            "hover": True,
            "keyboard": {"enabled": True, "bindToWindow": False},
            "multiselect": False,
            "selectConnectedEdges": True,
            "zoomView": True,
        },
        "layout": {
            "hierarchical": {
                "enabled": True,
                "direction": "LR",
                "sortMethod": "directed",
                "levelSeparation": 220,
                "nodeSpacing": 160,
            }
        },
        "manipulation": {"enabled": False},
        "physics": {"enabled": False},
    }
)
_VIS_CSS_PLACEHOLDER = "__CONTROLLED_VIS_NETWORK_CSS__"
_VIS_JS_PLACEHOLDER = "__CONTROLLED_VIS_NETWORK_JS__"
_FORBIDDEN_SCRIPT_MARKERS = ("eval(", "new function", "document.write")
_UUID_PATTERN = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
)
_REMOTE_TEXT_PATTERN = re.compile(
    r"(?i)(?:https?|javascript|vbscript|file|ftp|wss?|data)\s*:\s*\S+"
    r"|//(?:cdn\S*|\S*cdnjs\S*)"
)
_LEGACY_SCRIPT_FALLBACK = re.compile(
    r'pr=function\(t\)\{return"<script>"\+t\+"</"\+"script>"\},'
    r'vr=function\(t\)\{t\.write\(pr\(""\)\),t\.close\(\);'
    r'var e=t\.parentWindow\.Object;return t=null,e\},'
    r'gr=function\(\)\{try\{or=new ActiveXObject\("htmlfile"\)\}'
    r'catch\(t\)\{\}var t,e;gr=.*?return gr\(\)\};'
)
_QUOTED_UNSAFE_URI = re.compile(
    r'''(?is)["']\s*(?:https?|javascript|vbscript|file|ftp|wss?|data)\s*:'''
)
_QUOTED_PROTOCOL_RELATIVE = re.compile(r'''(?is)["']\s*//''')
_CSS_URL = re.compile(r"(?is)url\s*\(\s*(.*?)\s*\)")
_SVG_NAMESPACE = "http://www.w3.org/2000/svg"
_ESCAPED_SVG_NAMESPACE = r"\u0068ttp://www.w3.org/2000/svg"
_TOOLTIP_TEXT_ASSIGNMENT = "this.frame.innerText=t"
_RENDER_SEMAPHORE = threading.BoundedSemaphore(settings.graph_render_concurrency)


class HpnPyvisRenderer:
    """Renderiza una proyección ya construida, sin consultar ni persistir datos."""

    async def render(self, projection: HpnGraphProjection) -> RenderedGraphHtml:
        visual_graph = build_visual_graph(projection)
        _validate_visual_size(visual_graph)
        nonce = secrets.token_urlsafe(32)
        try:
            return await anyio.to_thread.run_sync(
                self._render_limited,
                visual_graph,
                nonce,
            )
        except GraphError:
            raise
        except Exception as exc:
            raise GraphError("GRAPH_RENDER_FAILED") from exc

    @staticmethod
    def _render_limited(
        visual_graph: VisualGraph,
        nonce: str,
    ) -> RenderedGraphHtml:
        with _RENDER_SEMAPHORE:
            return _render_visual_graph(visual_graph, nonce)


def build_visual_graph(projection: HpnGraphProjection) -> VisualGraph:
    """Reduce la proyección a aliases y campos visuales cerrados."""

    internal_ids = {
        str(projection.matrix.id),
        *(str(node.id) for node in projection.nodes),
        *(str(edge.id) for edge in projection.edges),
    }
    aliases = {
        node.id: f"n-{index:04d}"
        for index, node in enumerate(projection.nodes, start=1)
    }
    nodes: list[VisualNode] = []
    for node in projection.nodes:
        source_summary = node.source_summary.model_dump()
        source_status = _source_status(source_summary)
        node_type = _closed_node_type(node.type.value)
        review_status = _closed_review_status(node.review_status.value)
        label = _safe_visual_text(node.label, internal_ids)
        warning_flags = tuple(sorted(set(node.warning_flags)))
        nodes.append(
            VisualNode(
                alias=aliases[node.id],
                type=node_type,
                label=label,
                review_status=review_status,
                source_status=source_status,
                warning_flags=warning_flags,
                visual_group=(
                    f"{node_type}-{review_status}-{source_status.category}"
                ),
            )
        )

    edges: list[VisualEdge] = []
    for index, edge in enumerate(projection.edges, start=1):
        source_alias = aliases.get(edge.source)
        target_alias = aliases.get(edge.target)
        if source_alias is None or target_alias is None:
            raise GraphError("GRAPH_RELATION_INVALID")
        relation_type = _closed_relation_type(edge.relation_type.value)
        review_status = _closed_review_status(edge.review_status.value)
        edges.append(
            VisualEdge(
                alias=f"e-{index:04d}",
                source_alias=source_alias,
                target_alias=target_alias,
                relation_type=relation_type,
                label=_safe_visual_text(edge.label, internal_ids),
                review_status=review_status,
                warning_flags=tuple(sorted(set(edge.warning_flags))),
                visual_style=f"{relation_type}-{review_status}",
            )
        )

    warnings = {warning.code for warning in projection.warnings}
    if not nodes:
        warnings.add("GRAPH_EMPTY")
    if projection.matrix.read_only:
        warnings.add("GRAPH_MATRIX_ARCHIVED")
    return VisualGraph(
        nodes=tuple(nodes),
        edges=tuple(edges),
        summary=VisualSummary(
            node_count=len(nodes),
            edge_count=len(edges),
            disconnected_components=projection.summary.disconnected_components,
            has_directed_cycles=projection.summary.has_directed_cycles,
        ),
        warnings=tuple(sorted(warnings)),
        read_only=projection.matrix.read_only,
    )


def _render_visual_graph(
    visual_graph: VisualGraph,
    nonce: str,
) -> RenderedGraphHtml:
    network_class, pyvis_package_dir = _load_pyvis()
    network = network_class(
        height="100%",
        width="100%",
        directed=True,
        notebook=False,
        cdn_resources="in_line",
    )
    for node in visual_graph.nodes:
        type_style = _NODE_STYLES[node.type]
        review_style = _REVIEW_STYLES[node.review_status]
        network.add_node(
            node.alias,
            label=node.label,
            title=_node_tooltip(node),
            shape=type_style["shape"],
            color={
                "background": type_style["background"],
                "border": _SOURCE_BORDERS[node.source_status.category],
                "highlight": {
                    "background": type_style["background"],
                    "border": review_style["border"],
                },
            },
            borderWidth=2,
            borderWidthSelected=3,
            dashes=review_style["dashes"],
            font={"face": "Arial", "size": 14, "color": "#0f172a"},
            group=node.visual_group,
            physics=False,
        )
    parallel_totals = Counter(
        (edge.source_alias, edge.target_alias) for edge in visual_graph.edges
    )
    parallel_positions: defaultdict[tuple[str, str], int] = defaultdict(int)
    for edge in visual_graph.edges:
        style = _EDGE_STYLES[edge.relation_type]
        review_style = _REVIEW_STYLES[edge.review_status]
        pair = (edge.source_alias, edge.target_alias)
        position = parallel_positions[pair]
        parallel_positions[pair] += 1
        network.add_edge(
            edge.source_alias,
            edge.target_alias,
            id=edge.alias,
            label=edge.label,
            color={"color": style["color"], "highlight": style["color"]},
            dashes=bool(style["dashes"] or review_style["dashes"]),
            width=2,
            physics=False,
            smooth=_edge_smooth(position, parallel_totals[pair]),
        )
    network.set_options(json.dumps(dict(_VIS_OPTIONS), separators=(",", ":")))
    network_nodes, network_edges, _, _, _, options_json = network.get_network_data()
    graph_data = {"nodes": network_nodes, "edges": network_edges}
    graph_options = json.loads(options_json)
    vis_css, vis_js = _load_offline_assets(pyvis_package_dir)
    warning_messages = [
        _WARNING_MESSAGES[code]
        for code in visual_graph.warnings
        if code in _WARNING_MESSAGES
    ]
    template_dir = Path(__file__).resolve().parents[1] / "templates"
    environment = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        undefined=StrictUndefined,
    )
    environment.policies["json.dumps_kwargs"] = {
        "ensure_ascii": True,
        "sort_keys": True,
    }
    template = environment.get_template("hpn_graph.html.j2")
    rendered = template.render(
        nonce=nonce,
        graph_data=graph_data,
        graph_options=graph_options,
        summary=asdict(visual_graph.summary),
        warning_messages=warning_messages,
        read_only=visual_graph.read_only,
        is_empty=not visual_graph.nodes,
    )
    rendered = rendered.replace(_VIS_CSS_PLACEHOLDER, vis_css)
    rendered = rendered.replace(
        _VIS_JS_PLACEHOLDER,
        "" if not visual_graph.nodes else vis_js,
    )
    if _VIS_CSS_PLACEHOLDER in rendered or _VIS_JS_PLACEHOLDER in rendered:
        raise GraphError("GRAPH_RENDER_FAILED")
    _validate_rendered_html(rendered)
    html_bytes = len(rendered.encode("utf-8"))
    if html_bytes > settings.graph_max_html_bytes:
        raise GraphError("GRAPH_TOO_LARGE")
    return RenderedGraphHtml(html=rendered, nonce=nonce, html_bytes=html_bytes)


def _load_pyvis() -> tuple[Any, Path]:
    """Importa únicamente PyVis bajo demanda y conserva errores internos."""

    try:
        module = importlib.import_module("pyvis.network")
    except ModuleNotFoundError as exc:
        if exc.name in {"pyvis", "pyvis.network"}:
            raise GraphError("GRAPH_DEPENDENCY_NOT_AVAILABLE") from exc
        raise
    network_class = getattr(module, "Network", None)
    module_file = getattr(module, "__file__", None)
    if network_class is None or not module_file:
        raise GraphError("GRAPH_RENDER_FAILED")
    return network_class, Path(module_file).resolve().parent


def _load_offline_assets(pyvis_package_dir: Path) -> tuple[str, str]:
    try:
        package_root = pyvis_package_dir.resolve(strict=True)
        css_path = _resolve_package_asset(
            package_root,
            Path("lib/vis-9.1.2/vis-network.css"),
        )
        javascript_path = _resolve_package_asset(
            package_root,
            Path("lib/vis-9.1.2/vis-network.min.js"),
        )
        css = css_path.read_text(encoding="utf-8")
        javascript = javascript_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        raise GraphError("GRAPH_RENDER_FAILED") from exc
    if not css.strip() or not javascript.strip():
        raise GraphError("GRAPH_RENDER_FAILED")
    javascript = _sanitize_vendor_javascript(javascript)
    _validate_offline_css(css)
    _validate_offline_javascript(javascript)
    return css, javascript


def _resolve_package_asset(package_root: Path, relative_path: Path) -> Path:
    candidate = (package_root / relative_path).resolve(strict=True)
    candidate.relative_to(package_root)
    if not candidate.is_file():
        raise ValueError("GRAPH_RENDER_FAILED")
    return candidate


def _sanitize_vendor_javascript(javascript: str) -> str:
    """Retira metadata remota y una rama HTML heredada no necesaria."""

    sanitized = re.sub(r"^/\*\*.*?\*/\s*", "", javascript, count=1, flags=re.DOTALL)
    sanitized, fallback_count = _LEGACY_SCRIPT_FALLBACK.subn(
        "pr=function(t){return t},vr=function(t){return Object},"
        "gr=function(){return Object};",
        sanitized,
        count=1,
    )
    if fallback_count != 1:
        raise GraphError("GRAPH_RENDER_FAILED")
    sanitized = re.sub(
        r"\n?//#\s*sourceMappingURL=.*$",
        "",
        sanitized,
        count=1,
        flags=re.MULTILINE,
    )

    def replace_url(match: re.Match[str]) -> str:
        url = match.group(0)
        if url == _SVG_NAMESPACE:
            return _ESCAPED_SVG_NAMESPACE
        return "offline-reference-removed"

    sanitized = re.sub(
        r'''(?i)https?://[^"'\s*]+''',
        replace_url,
        sanitized,
    )
    return sanitized


def _validate_offline_javascript(javascript: str) -> None:
    normalized = _normalize_security_escapes(javascript)
    if normalized.count(_SVG_NAMESPACE) != 2:
        raise GraphError("GRAPH_RENDER_FAILED")
    without_namespace = normalized.replace(_SVG_NAMESPACE, "")
    compact = re.sub(r"\s+", "", without_namespace)
    lowered = compact.lower()
    if _QUOTED_UNSAFE_URI.search(compact):
        raise GraphError("GRAPH_RENDER_FAILED")
    if _QUOTED_PROTOCOL_RELATIVE.search(compact):
        raise GraphError("GRAPH_RENDER_FAILED")
    if any(
        marker in lowered
        for marker in (
            "sourcemappingurl",
            "<script",
            "</script",
            "<!--",
            "-->",
            "javascript:",
            "document.write",
            "eval(",
            "newfunction",
            'createelement("style")',
            "createelement('style')",
            'cr("style")',
            "insertrule",
        )
    ):
        raise GraphError("GRAPH_RENDER_FAILED")
    if _TOOLTIP_TEXT_ASSIGNMENT not in javascript:
        raise GraphError("GRAPH_RENDER_FAILED")


def _validate_offline_css(css: str) -> None:
    normalized = _normalize_security_escapes(css)
    for match in _CSS_URL.finditer(normalized):
        value = match.group(1).strip().strip("\"'")
        if re.fullmatch(
            r"(?is)data:image/png;base64,[a-z0-9+/=\s]+",
            value,
        ) is None:
            raise GraphError("GRAPH_RENDER_FAILED")
    without_data_images = _CSS_URL.sub("", normalized)
    compact = re.sub(r"\s+", "", without_data_images)
    lowered = compact.lower()
    if _QUOTED_UNSAFE_URI.search(compact):
        raise GraphError("GRAPH_RENDER_FAILED")
    if _QUOTED_PROTOCOL_RELATIVE.search(compact):
        raise GraphError("GRAPH_RENDER_FAILED")
    if any(
        marker in lowered
        for marker in (
            "@import",
            "@font-face",
            "sourcemappingurl",
            "<style",
            "</style",
            "<!--",
            "-->",
        )
    ):
        raise GraphError("GRAPH_RENDER_FAILED")


def _normalize_security_escapes(value: str) -> str:
    """Normaliza escapes relevantes antes de auditar esquemas y markup."""

    normalized = value
    for _ in range(2):
        normalized = html.unescape(normalized).replace(r"\/", "/")
        normalized = re.sub(
            r"(?i)\\u([0-9a-f]{4})|\\x([0-9a-f]{2})",
            lambda match: chr(int(match.group(1) or match.group(2), 16)),
            normalized,
        )
    return normalized


def _validate_visual_size(visual_graph: VisualGraph) -> None:
    payload = json.dumps(
        asdict(visual_graph),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(payload) > settings.graph_max_html_bytes:
        raise GraphError("GRAPH_TOO_LARGE")


def _validate_rendered_html(rendered: str) -> None:
    normalized = _normalize_security_escapes(rendered)
    normalized = normalized.replace(_SVG_NAMESPACE, "")
    normalized = _CSS_URL.sub("", normalized)
    lowered = normalized.lower()
    if _QUOTED_UNSAFE_URI.search(normalized):
        raise GraphError("GRAPH_RENDER_FAILED")
    if _QUOTED_PROTOCOL_RELATIVE.search(normalized):
        raise GraphError("GRAPH_RENDER_FAILED")
    if any(
        marker in lowered
        for marker in ("//cdn", "cdnjs", "unpkg", "jsdelivr", "googleapis")
    ):
        raise GraphError("GRAPH_RENDER_FAILED")
    if any(marker in lowered for marker in _FORBIDDEN_SCRIPT_MARKERS):
        raise GraphError("GRAPH_RENDER_FAILED")


def _safe_visual_text(value: str, internal_ids: set[str]) -> str:
    normalized = unicodedata.normalize("NFC", html.unescape(value))
    without_controls = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("C")
    )
    safe = _UUID_PATTERN.sub("[identificador omitido]", without_controls)
    for internal_id in internal_ids:
        safe = safe.replace(internal_id, "[identificador omitido]")
    safe = _REMOTE_TEXT_PATTERN.sub("[referencia externa omitida]", safe)
    for marker in ("cdnjs", "unpkg", "jsdelivr", "googleapis"):
        safe = re.sub(marker, "[referencia externa omitida]", safe, flags=re.IGNORECASE)
    return " ".join(safe.split())


def _node_tooltip(node: VisualNode) -> str:
    warnings = ", ".join(node.warning_flags) if node.warning_flags else "ninguno"
    tooltip = (
        f"Tipo: {node.type}; etiqueta: {node.label}; revisión: {node.review_status}; "
        f"fuentes: total {node.source_status.total}, válidas "
        f"{node.source_status.valid}, obsoletas {node.source_status.stale}, "
        f"no disponibles {node.source_status.unavailable}; "
        f"advertencias: {warnings}"
    )
    limit = settings.graph_max_tooltip_length
    if len(tooltip) <= limit:
        return tooltip
    return tooltip[:limit].rstrip()


def _edge_smooth(position: int, total: int) -> dict[str, object]:
    """Separa multiaristas con una curva fija y determinista."""

    if total <= 1:
        return {"enabled": True, "type": "cubicBezier"}
    curve_index = position // 2
    return {
        "enabled": True,
        "type": "curvedCW" if position % 2 == 0 else "curvedCCW",
        "roundness": min(0.15 + curve_index * 0.08, 0.47),
    }


def _source_status(summary: dict[str, Any]) -> VisualSourceStatus:
    if summary["total"] == 0:
        category: VisualSourceCategory = "none"
        return VisualSourceStatus(category=category, **_source_counts(summary))
    populated = [
        status
        for status in ("valid", "stale", "unavailable")
        if summary[status]
    ]
    if len(populated) != 1:
        category = "mixed"
    else:
        category = _closed_source_status(populated[0])
    return VisualSourceStatus(category=category, **_source_counts(summary))


def _source_counts(summary: dict[str, Any]) -> dict[str, int]:
    return {
        "total": int(summary["total"]),
        "valid": int(summary["valid"]),
        "stale": int(summary["stale"]),
        "unavailable": int(summary["unavailable"]),
    }


def _closed_node_type(value: str) -> VisualNodeType:
    if value not in _NODE_STYLES:
        raise GraphError("GRAPH_RENDER_FAILED")
    return cast(VisualNodeType, value)


def _closed_review_status(value: str) -> VisualReviewStatus:
    if value not in _REVIEW_STYLES:
        raise GraphError("GRAPH_RENDER_FAILED")
    return cast(VisualReviewStatus, value)


def _closed_source_status(value: str) -> VisualSourceCategory:
    if value not in _SOURCE_BORDERS:
        raise GraphError("GRAPH_RENDER_FAILED")
    return cast(VisualSourceCategory, value)


def _closed_relation_type(value: str) -> VisualRelationType:
    if value not in _EDGE_STYLES:
        raise GraphError("GRAPH_RELATION_INVALID")
    return cast(VisualRelationType, value)
