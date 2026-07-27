"""CLI explícita para validar y administrar fuentes jurídicas locales."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.database.models.document import LegalValidityStatus  # noqa: E402
from app.database.session import database_session_manager  # noqa: E402
from app.schemas.managed_corpus import ManagedCorpusBatchResult, ManagedCorpusResult  # noqa: E402
from app.services.managed_corpus_service import (  # noqa: E402
    ManagedCorpusError,
    ManagedCorpusService,
)


DEFAULT_MANIFEST = PROJECT_ROOT / "managed_corpus" / "manifest.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Administra un corpus local sin descarga, extracción ni indexación automática"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true", dest="as_json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Valida sin escribir")
    import_parser = commands.add_parser("import", help="Importa pendiente de revisión")
    import_parser.add_argument("--continue-on-error", action="store_true")
    commands.add_parser("status", help="Consulta estados técnicos seguros")
    review = commands.add_parser("review", help="Aplica una decisión humana explícita")
    review.add_argument("--source-key", required=True)
    review.add_argument("--decision", choices=("approve", "reject", "pending"), required=True)
    review.add_argument(
        "--legal-validity",
        choices=tuple(item.value for item in LegalValidityStatus),
    )
    review.add_argument("--confirm", action="store_true")
    promote = commands.add_parser("promote", help="Promueve un documento existente")
    promote.add_argument("--source-key", required=True)
    promote.add_argument("--document-id", type=UUID, required=True)
    promote.add_argument("--confirm", action="store_true")
    return parser


async def execute(args: argparse.Namespace) -> ManagedCorpusBatchResult | ManagedCorpusResult:
    manifest = ManagedCorpusService.load_manifest(args.manifest)
    async with database_session_manager.get_session_factory()() as session:
        service = ManagedCorpusService(session)
        if args.command == "validate":
            return await service.validate(manifest)
        if args.command == "import":
            return await service.import_documents(
                manifest,
                continue_on_error=args.continue_on_error,
            )
        if args.command == "status":
            return await service.status(manifest)
        if args.command == "review":
            legal_validity = (
                LegalValidityStatus(args.legal_validity)
                if args.legal_validity is not None
                else None
            )
            return await service.review(
                manifest,
                source_key=args.source_key,
                decision=args.decision,
                legal_validity=legal_validity,
                confirmed=args.confirm,
            )
        if args.command == "promote":
            return await service.promote(
                manifest,
                source_key=args.source_key,
                document_id=args.document_id,
                confirmed=args.confirm,
            )
    raise ManagedCorpusError("MANAGED_CORPUS_OPERATION_INVALID", exit_code=2)


def _payload(result: ManagedCorpusBatchResult | ManagedCorpusResult) -> dict[str, Any]:
    return result.model_dump(mode="json")


def _print_result(
    result: ManagedCorpusBatchResult | ManagedCorpusResult, *, as_json: bool
) -> None:
    payload = _payload(result)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    if isinstance(result, ManagedCorpusBatchResult):
        print(
            f"{result.operation.value}: éxito={result.succeeded} "
            f"conflictos={result.conflicts} fallos={result.failed}"
        )
        for item in result.results:
            reason = item.safe_reason_code or "OK"
            print(f"{item.source_key}: {item.status.value} ({reason})")
    else:
        reason = result.safe_reason_code or "OK"
        print(f"{result.source_key}: {result.status.value} ({reason})")


def _result_exit_code(result: ManagedCorpusBatchResult | ManagedCorpusResult) -> int:
    if isinstance(result, ManagedCorpusBatchResult):
        if result.failed:
            return 2
        if result.conflicts:
            return 3
        return 0
    return 3 if result.status.value == "conflict" else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = asyncio.run(execute(args))
        _print_result(result, as_json=args.as_json)
        return _result_exit_code(result)
    except ManagedCorpusError as exc:
        safe = {"status": "error", "safe_reason_code": exc.code}
        if args.as_json:
            print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        else:
            print(f"error: {exc.code}")
        return exc.exit_code
    finally:
        asyncio.run(database_session_manager.dispose())


if __name__ == "__main__":
    raise SystemExit(main())
