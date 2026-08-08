"""Coleta auditável dos datasets públicos prioritários da Epoch AI."""

import csv
import hashlib
import io
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

from export_excel import write_tables_workbook

ROOT = Path(__file__).resolve().parent
EPOCH_DIR = ROOT / "data" / "epoch"
RAW_DIR = EPOCH_DIR / "raw"
SOURCE_LOG_PATH = EPOCH_DIR / "source_history.csv"
OUTPUT_DIR = ROOT / "outputs Epoch AI"

# Downloads oficiais da Epoch AI. Os ZIPs preservam as tabelas relacionadas
# juntas, para que cada snapshot tenha uma origem inequívoca.
SOURCES = {
    "ECI e benchmarks": "https://epoch.ai/data/benchmark_data.zip",
    "Capacidade de chips": "https://epoch.ai/data/ai_chip_owners.zip",
    "Data centers": "https://epoch.ai/data/data_centers/data_centers.zip",
    "Empresas de IA": "https://epoch.ai/data/ai_companies.zip",
}

SOURCE_LOG_FIELDS = [
    "run_id", "collected_at_utc", "source", "url", "sha256", "bytes",
    "archive_file", "content_changed", "status",
]


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Radar-IA/1.0", "Accept": "application/zip"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def _read_log() -> list[dict]:
    if not SOURCE_LOG_PATH.exists():
        return []
    with SOURCE_LOG_PATH.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _append_log(rows: list[dict]) -> None:
    EPOCH_DIR.mkdir(parents=True, exist_ok=True)
    exists = SOURCE_LOG_PATH.exists()
    with SOURCE_LOG_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SOURCE_LOG_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def _zip_csv(data: bytes, filename: str) -> tuple[list[str], list[dict]]:
    with ZipFile(io.BytesIO(data)) as archive:
        with archive.open(filename) as file:
            text = io.TextIOWrapper(file, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(text)
            return list(reader.fieldnames or []), list(reader)


def _table_from_zip(data: bytes, filename: str) -> tuple[list[str], list[dict]]:
    return _zip_csv(data, filename)


def _rows_for_sheet(headers: list[str], records: list[dict]) -> list[list]:
    return [[(header, 1) for header in headers]] + [
        [record.get(header, "") for header in headers] for record in records
    ]


def _widths(headers: list[str]) -> list[int]:
    return [min(max(len(header) + 3, 14), 34) for header in headers]


def _make_sheets(datasets: dict[str, tuple[list[str], list[dict]]], log_rows: list[dict], run_id: str) -> list[tuple[str, list, list, bool]]:
    overview = [
        [("Epoch AI — snapshot de dados", 1), "", "", ""], [],
        [("Execução UTC", 2), run_id],
        [("Uso", 2), "Cada execução cria um novo Excel. Os ZIPs oficiais são arquivados somente quando o conteúdo muda (SHA-256)."],
        [("ECI", 2), "Score, data de lançamento, organização, país e acessibilidade."],
        [("Capacidade", 2), "Séries por organização e por chip em equivalentes H100."],
        [("Data centers", 2), "Snapshot, cronologia (inclusive projeções da Epoch) e quantidades de chips."],
        [("Empresas", 2), "Cadastro, funding, receita, equipe, uso e gasto de compute."],
        [("Atribuição", 2), "Epoch AI — datasets públicos sob CC-BY. Consulte a aba Fontes para URLs e hashes."],
    ]
    sheets = [("Visão geral", overview, [28, 100, 16, 16], False)]
    order = [
        ("ECI", "ECI"),
        ("Capacidade por org.", "Capacidade - organização"),
        ("Capacidade por chip", "Capacidade - chip"),
        ("Capacidade trimestral", "Capacidade - trimestre"),
        ("Data centers", "Data centers"),
        ("Timeline data centers", "Timeline data centers"),
        ("Chips em data centers", "Chips data centers"),
        ("Empresas", "Empresas"),
        ("Funding rounds", "Funding rounds"),
        ("Receita", "Receita"),
        ("Equipe", "Equipe"),
        ("Uso", "Uso"),
        ("Gasto de compute", "Gasto de compute"),
    ]
    for key, name in order:
        if key not in datasets:
            continue
        headers, records = datasets[key]
        sheets.append((name, _rows_for_sheet(headers, records), _widths(headers), True))
    log_headers = SOURCE_LOG_FIELDS
    sheets.append(("Fontes", _rows_for_sheet(log_headers, log_rows), _widths(log_headers), True))
    return sheets


def run_epoch_collection(run_id: str, collected_at_utc: str) -> dict:
    """Download current public sources, archive changed versions, and write Excel."""
    previous_log = _read_log()
    known_hashes = {row.get("sha256") for row in previous_log if row.get("sha256")}
    raw_by_source: dict[str, bytes] = {}
    current_log = []
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for source, url in SOURCES.items():
        try:
            data = _download(url)
            digest = hashlib.sha256(data).hexdigest()
            changed = digest not in known_hashes
            archive_file = ""
            if changed:
                safe_name = source.lower().replace(" ", "_").replace("ç", "c")
                archive_file = f"{safe_name}_{run_id}.zip"
                (RAW_DIR / archive_file).write_bytes(data)
            raw_by_source[source] = data
            current_log.append({
                "run_id": run_id, "collected_at_utc": collected_at_utc, "source": source,
                "url": url, "sha256": digest, "bytes": len(data), "archive_file": archive_file,
                "content_changed": "Yes" if changed else "No", "status": "Downloaded",
            })
        except Exception as error:
            current_log.append({
                "run_id": run_id, "collected_at_utc": collected_at_utc, "source": source,
                "url": url, "sha256": "", "bytes": "", "archive_file": "",
                "content_changed": "", "status": f"Error: {error}",
            })

    datasets = {}
    table_sources = [
        ("ECI", "ECI e benchmarks", "epoch_capabilities_index.csv"),
        ("Capacidade por org.", "Capacidade de chips", "cumulative_by_designer.csv"),
        ("Capacidade por chip", "Capacidade de chips", "cumulative_by_chip_type.csv"),
        ("Capacidade trimestral", "Capacidade de chips", "quarters_by_chip_type.csv"),
        ("Data centers", "Data centers", "data_centers.csv"),
        ("Timeline data centers", "Data centers", "data_center_timelines.csv"),
        ("Chips em data centers", "Data centers", "data_center_chip_quantities.csv"),
        ("Empresas", "Empresas de IA", "ai_companies.csv"),
        ("Funding rounds", "Empresas de IA", "ai_companies_funding_rounds.csv"),
        ("Receita", "Empresas de IA", "ai_companies_revenue_reports.csv"),
        ("Equipe", "Empresas de IA", "ai_companies_staff_reports.csv"),
        ("Uso", "Empresas de IA", "ai_companies_usage_reports.csv"),
        ("Gasto de compute", "Empresas de IA", "ai_companies_compute_spend.csv"),
    ]
    for key, source, filename in table_sources:
        if source not in raw_by_source:
            continue
        try:
            datasets[key] = _table_from_zip(raw_by_source[source], filename)
        except Exception as error:
            current_log.append({
                "run_id": run_id, "collected_at_utc": collected_at_utc, "source": f"{source}: {filename}",
                "url": SOURCES[source], "sha256": "", "bytes": "", "archive_file": "",
                "content_changed": "", "status": f"Error reading ZIP: {error}",
            })
    _append_log(current_log)
    workbook_path = OUTPUT_DIR / f"Epoch_AI_{run_id}.xlsx"
    write_tables_workbook(workbook_path, _make_sheets(datasets, previous_log + current_log, run_id))
    successes = sum(row["status"] == "Downloaded" for row in current_log)
    return {"workbook_path": workbook_path, "sources_downloaded": successes, "sources_total": len(SOURCES)}
