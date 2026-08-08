#!/usr/bin/env python3
"""Coleta mensal do Radar IA e geração do Excel a partir do histórico local."""

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
HISTORY_PATH = DATA_DIR / "model_history.csv"
RUN_LOG_PATH = DATA_DIR / "run_log.csv"
ENV_PATH = ROOT / ".env"
ENDPOINT = "https://artificialanalysis.ai/api/v2/language/models/free"

FIELDS = [
    "reference_month", "collected_at_utc", "api_tier", "intelligence_index_version",
    "model_id", "model_slug", "model_name", "creator_id", "model_creator",
    "release_date", "intelligence_index", "coding_index", "agentic_index",
    "median_output_tokens_per_second", "median_time_to_first_token_seconds",
    "intelligence_index_cost_per_task_usd", "price_1m_input_tokens_usd",
    "price_1m_output_tokens_usd", "model_access_type", "access_classification_source",
    "epoch_model_name", "epoch_accessibility", "change_fields", "source_url",
]

RUN_LOG_FIELDS = [
    "run_id", "collected_at_utc", "reference_month", "models_received", "new_models",
    "changed_models", "unchanged_models", "api_tier", "intelligence_index_version",
    "epoch_access_status",
]

COMPARISON_FIELDS = [
    "model_name", "model_slug", "model_creator", "release_date", "intelligence_index",
    "coding_index", "agentic_index", "median_output_tokens_per_second",
    "median_time_to_first_token_seconds", "intelligence_index_cost_per_task_usd",
    "price_1m_input_tokens_usd", "price_1m_output_tokens_usd", "model_access_type",
    "access_classification_source", "epoch_model_name", "epoch_accessibility",
]


def read_env(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def nested(item, *keys):
    value = item
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def request_page(api_key: str, page: int) -> dict:
    url = f"{ENDPOINT}?{urlencode({'page': page})}"
    request = Request(url, headers={"x-api-key": api_key, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=45) as response:
            return json.load(response)
    except HTTPError as error:
        body = error.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"API respondeu HTTP {error.code}: {body}") from error
    except URLError as error:
        raise RuntimeError(f"Não foi possível conectar à API: {error.reason}") from error


def fetch_all(api_key: str) -> tuple[dict, list]:
    first = request_page(api_key, 1)
    data = list(first.get("data") or [])
    pagination = first.get("pagination") or {}
    total_pages = int(pagination.get("total_pages") or 1)
    for page in range(2, total_pages + 1):
        payload = request_page(api_key, page)
        data.extend(payload.get("data") or [])
    return first, data


def normalize(item: dict, metadata: dict, collected_at: datetime, access_index=None) -> dict:
    evaluations = item.get("evaluations") or {}
    pricing = item.get("pricing") or {}
    performance = item.get("performance") or {}
    creator = item.get("model_creator") or {}
    cost = item.get("artificial_analysis_intelligence_index_cost") or {}
    row = {
        "reference_month": collected_at.strftime("%Y-%m"),
        "collected_at_utc": collected_at.isoformat().replace("+00:00", "Z"),
        "api_tier": metadata.get("tier"),
        "intelligence_index_version": (
            metadata.get("intelligence_index_version")
            or metadata.get("artificial_analysis_intelligence_index_version")
            or nested(evaluations, "artificial_analysis_intelligence_index_version")
        ),
        "model_id": item.get("id"),
        "model_slug": item.get("slug"),
        "model_name": item.get("name"),
        "creator_id": creator.get("id"),
        "model_creator": creator.get("name"),
        "release_date": item.get("release_date"),
        "intelligence_index": evaluations.get("artificial_analysis_intelligence_index"),
        "coding_index": evaluations.get("artificial_analysis_coding_index"),
        "agentic_index": evaluations.get("artificial_analysis_agentic_index"),
        "median_output_tokens_per_second": (
            performance.get("median_output_tokens_per_second")
            or item.get("median_output_tokens_per_second")
        ),
        "median_time_to_first_token_seconds": (
            performance.get("median_time_to_first_token_seconds")
            or item.get("median_time_to_first_token_seconds")
        ),
        "intelligence_index_cost_per_task_usd": nested(cost, "cost_per_task", "total_cost"),
        "price_1m_input_tokens_usd": pricing.get("price_1m_input_tokens"),
        "price_1m_output_tokens_usd": pricing.get("price_1m_output_tokens"),
        "source_url": ENDPOINT,
    }
    if access_index:
        row.update(access_index.classify(row["model_name"]))
    else:
        row.update({
            "model_access_type": "Unknown",
            "access_classification_source": "Epoch AI unavailable",
            "epoch_model_name": None,
            "epoch_accessibility": None,
        })
    return row


def _normalised_value(value):
    return "" if value is None else str(value).strip()


def _changed_fields(previous: dict, current: dict) -> list[str]:
    return [field for field in COMPARISON_FIELDS if _normalised_value(previous.get(field)) != _normalised_value(current.get(field))]


def append_history(rows: list[dict]) -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    existing_rows = []
    if HISTORY_PATH.exists():
        with HISTORY_PATH.open(newline="", encoding="utf-8") as file:
            existing_rows = list(csv.DictReader(file))
    for row in existing_rows:
        if not row.get("change_fields"):
            row["change_fields"] = "initial_record"
    latest_by_model = {row["model_id"]: row for row in existing_rows if row.get("model_id")}
    new_models = changed_models = unchanged_models = 0
    for row in rows:
        previous = latest_by_model.get(row["model_id"])
        if previous is None:
            row["change_fields"] = "initial_record"
            existing_rows.append(row)
            latest_by_model[row["model_id"]] = row
            new_models += 1
        else:
            fields = _changed_fields(previous, row)
            if fields:
                row["change_fields"] = ", ".join(fields)
                existing_rows.append(row)
                latest_by_model[row["model_id"]] = row
                changed_models += 1
            else:
                unchanged_models += 1
    temporary_path = HISTORY_PATH.with_suffix(".tmp")
    with temporary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(({field: row.get(field, "") for field in FIELDS} for row in existing_rows))
    temporary_path.replace(HISTORY_PATH)
    return {"new_models": new_models, "changed_models": changed_models, "unchanged_models": unchanged_models}


def append_run_log(summary: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    write_header = not RUN_LOG_PATH.exists()
    with RUN_LOG_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=RUN_LOG_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(summary)


def build_workbook(run_id: str) -> Path:
    from export_excel import build_workbook as export_excel

    return export_excel(HISTORY_PATH, RUN_LOG_PATH, ROOT / "outputs AA", run_id)


def main() -> None:
    api_key = os.environ.get("AA_API_KEY") or read_env(ENV_PATH).get("AA_API_KEY")
    if not api_key or api_key == "cole_a_sua_chave_aqui":
        raise RuntimeError("Defina AA_API_KEY no arquivo .env antes de executar.")
    collected_at = datetime.now(timezone.utc)
    metadata, models = fetch_all(api_key)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"language_models_{collected_at.strftime('%Y-%m-%dT%H%M%SZ')}.json"
    raw_path.write_text(json.dumps({"metadata": metadata, "data": models}, ensure_ascii=False, indent=2), encoding="utf-8")
    access_index = None
    epoch_access_status = "Unavailable"
    try:
        from epoch_access import fetch_epoch_access_index

        access_index, epoch_csv = fetch_epoch_access_index()
        epoch_path = RAW_DIR / f"epoch_access_{collected_at.strftime('%Y-%m-%dT%H%M%SZ')}.csv"
        epoch_path.write_text(epoch_csv, encoding="utf-8")
        epoch_access_status = "Downloaded"
    except Exception as error:
        print(f"Aviso: classificação open weights indisponível nesta coleta: {error}", file=sys.stderr)
    rows = [normalize(item, metadata, collected_at, access_index) for item in models]
    run_id = collected_at.strftime("%Y-%m-%dT%H%M%SZ")
    changes = append_history(rows)
    append_run_log({
        "run_id": run_id,
        "collected_at_utc": collected_at.isoformat().replace("+00:00", "Z"),
        "reference_month": collected_at.strftime("%Y-%m"),
        "models_received": len(models),
        **changes,
        "api_tier": metadata.get("tier"),
        "intelligence_index_version": metadata.get("intelligence_index_version") or metadata.get("artificial_analysis_intelligence_index_version"),
        "epoch_access_status": epoch_access_status,
    })
    workbook_path = build_workbook(run_id)
    print(f"Coleta concluída: {len(models)} modelos recebidos; {changes['new_models']} novos, {changes['changed_models']} alterados e {changes['unchanged_models']} sem mudança. Excel: {workbook_path.name}")
    try:
        from epoch_collector import run_epoch_collection

        epoch_result = run_epoch_collection(run_id, collected_at.isoformat().replace("+00:00", "Z"))
        print(f"Epoch AI concluído: {epoch_result['sources_downloaded']}/{epoch_result['sources_total']} fontes. Excel: {epoch_result['workbook_path'].name}")
    except Exception as error:
        # A coleta AA já concluída continua válida mesmo se uma fonte pública da
        # Epoch estiver temporariamente indisponível.
        print(f"Aviso: coleta Epoch AI não concluída: {error}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Erro: {error}", file=sys.stderr)
        sys.exit(1)
