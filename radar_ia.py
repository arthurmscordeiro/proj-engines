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
ENV_PATH = ROOT / ".env"
ENDPOINT = "https://artificialanalysis.ai/api/v2/language/models/free"

FIELDS = [
    "reference_month", "collected_at_utc", "api_tier", "intelligence_index_version",
    "model_id", "model_slug", "model_name", "creator_id", "model_creator",
    "release_date", "intelligence_index", "coding_index", "agentic_index",
    "median_output_tokens_per_second", "median_time_to_first_token_seconds",
    "intelligence_index_cost_per_task_usd", "price_1m_input_tokens_usd",
    "price_1m_output_tokens_usd", "source_url",
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


def normalize(item: dict, metadata: dict, collected_at: datetime) -> dict:
    evaluations = item.get("evaluations") or {}
    pricing = item.get("pricing") or {}
    performance = item.get("performance") or {}
    creator = item.get("model_creator") or {}
    cost = item.get("artificial_analysis_intelligence_index_cost") or {}
    return {
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


def append_history(rows: list[dict]) -> int:
    DATA_DIR.mkdir(exist_ok=True)
    existing = set()
    if HISTORY_PATH.exists():
        with HISTORY_PATH.open(newline="", encoding="utf-8") as file:
            existing = {(row["reference_month"], row["model_id"]) for row in csv.DictReader(file)}
    new_rows = [row for row in rows if (row["reference_month"], row["model_id"]) not in existing]
    write_header = not HISTORY_PATH.exists()
    with HISTORY_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)
    return len(new_rows)


def build_workbook(run_id: str) -> Path:
    from export_excel import build_workbook as export_excel

    return export_excel(HISTORY_PATH, ROOT / "outputs", run_id)


def main() -> None:
    api_key = os.environ.get("AA_API_KEY") or read_env(ENV_PATH).get("AA_API_KEY")
    if not api_key or api_key == "cole_a_sua_chave_aqui":
        raise RuntimeError("Defina AA_API_KEY no arquivo .env antes de executar.")
    collected_at = datetime.now(timezone.utc)
    metadata, models = fetch_all(api_key)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"language_models_{collected_at.strftime('%Y-%m-%dT%H%M%SZ')}.json"
    raw_path.write_text(json.dumps({"metadata": metadata, "data": models}, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [normalize(item, metadata, collected_at) for item in models]
    added = append_history(rows)
    run_id = collected_at.strftime("%Y-%m-%dT%H%M%SZ")
    workbook_path = build_workbook(run_id)
    print(f"Coleta concluída: {len(models)} modelos recebidos; {added} linhas novas no histórico. Excel: {workbook_path.name}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Erro: {error}", file=sys.stderr)
        sys.exit(1)
