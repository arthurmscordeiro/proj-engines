"""Gera snapshots .xlsx do Radar IA usando somente a biblioteca padrão do Python."""

import csv
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def _number(value):
    return None if value in (None, "") else float(value)


def _column_name(number):
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _cell(column, row, value, style=0):
    reference = f"{_column_name(column)}{row}"
    style_attribute = f' s="{style}"' if style else ""
    if value is None or value == "":
        return f'<c r="{reference}"{style_attribute}/>'
    if isinstance(value, (int, float)):
        return f'<c r="{reference}"{style_attribute} t="n"><v>{value}</v></c>'
    return f'<c r="{reference}"{style_attribute} t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def _worksheet(rows, widths, frozen=False, merge_title=False):
    xml_rows = []
    for row_number, values in enumerate(rows, start=1):
        xml_cells = []
        for column, entry in enumerate(values, start=1):
            value, style = entry if isinstance(entry, tuple) else (entry, 0)
            xml_cells.append(_cell(column, row_number, value, style))
        height = ' ht="30" customHeight="1"' if row_number == 1 and merge_title else ""
        xml_rows.append(f'<row r="{row_number}"{height}>{"".join(xml_cells)}</row>')
    columns = "".join(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>' for index, width in enumerate(widths, start=1))
    view = '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
    if frozen:
        view += '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
    view += '</sheetView></sheetViews>'
    merge = '<mergeCells count="1"><mergeCell ref="A1:F1"/></mergeCells>' if merge_title else ""
    dimension = f'<dimension ref="A1:{_column_name(len(widths))}{len(rows)}"/>'
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{dimension}{view}<cols>{columns}</cols><sheetData>{"".join(xml_rows)}</sheetData>{merge}</worksheet>'''


def _styles():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="1"><numFmt numFmtId="164" formatCode="$#,##0.000"/></numFmts>
  <fonts count="3"><font><sz val="11"/><name val="Aptos"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="16"/><name val="Aptos"/></font><font><b/><color rgb="FF102A43"/><sz val="11"/><name val="Aptos"/></font></fonts>
  <fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF102A43"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE8F1FA"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="5">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


def write_tables_workbook(output_path: Path, sheets: list[tuple[str, list, list, bool]]) -> Path:
    """Write a simple multi-sheet workbook from tabular data using stdlib only.

    Each sheet is ``(name, rows, widths, freeze_header)``.  Keeping this tiny
    writer in-house avoids a third-party dependency on corporate machines.
    """
    if not sheets:
        raise ValueError("É necessário informar ao menos uma aba para o Excel.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    content_types = f'''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>{overrides}</Types>'''
    relationships = '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    workbook_sheets = "".join(
        f'<sheet name="{escape(name[:31])}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _, _, _) in enumerate(sheets, start=1)
    )
    workbook = f'''<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{workbook_sheets}</sheets></workbook>'''
    worksheet_relationships = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    workbook_relationships = f'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{worksheet_relationships}<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_relationships)
        archive.writestr("xl/styles.xml", _styles())
        for index, (_, rows, widths, frozen) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet(rows, widths, frozen=frozen))
    return output_path


def build_workbook(history_path: Path, run_log_path: Path, output_dir: Path, run_id: str) -> Path:
    with history_path.open(newline="", encoding="utf-8") as source:
        history_rows = list(csv.DictReader(source))
    history_rows.sort(key=lambda row: (row["collected_at_utc"], row["model_name"]))
    latest_by_model = {row["model_id"]: row for row in history_rows if row.get("model_id")}
    latest_rows = list(latest_by_model.values())
    latest_rows.sort(key=lambda row: _number(row["intelligence_index"]) or float("-inf"), reverse=True)
    with run_log_path.open(newline="", encoding="utf-8") as source:
        run_rows = list(csv.DictReader(source))
    latest_run = run_rows[-1]
    open_weights_count = sum(row.get("model_access_type") == "Open weights" for row in latest_rows)
    proprietary_count = sum(row.get("model_access_type") == "Proprietary" for row in latest_rows)
    unknown_access_count = len(latest_rows) - open_weights_count - proprietary_count

    overview = [[("Radar IA — histórico de modelos", 1), "", "", "", "", ""], [],
        [("Última execução", 2), latest_run["collected_at_utc"]], [("Modelos consultados", 2), _number(latest_run["models_received"])],
        [("Modelos novos nesta execução", 2), _number(latest_run["new_models"])], [("Modelos alterados nesta execução", 2), _number(latest_run["changed_models"])],
        [("Modelos sem mudança", 2), _number(latest_run["unchanged_models"])], [("Eventos no histórico", 2), len(history_rows)],
        [("Versão do Intelligence Index", 2), latest_run.get("intelligence_index_version") or "Não informada pela API"], [],
        [("Modelos open weights", 2), open_weights_count], [("Modelos proprietários", 2), proprietary_count], [("Classificação ainda desconhecida", 2), unknown_access_count], [],
        [("Fonte e uso", 3), "Dados coletados da API gratuita da Artificial Analysis."],
        [("Metodologia", 3), "O histórico preserva a versão do índice para evitar comparações silenciosas entre metodologias diferentes."],
        [("Open weights", 3), "Classificação cruzada com o dataset de modelos da Epoch AI. Registros sem correspondência ficam como Unknown, sem inferência manual."],
        [("Atualização", 3), "Execute python radar_ia.py uma vez por mês. O comando adiciona o mês novo e cria este Excel."],
        [("Atribuição", 3), "https://artificialanalysis.ai/ | https://epoch.ai/data/ai-models"]]

    current_headers = ["Posição", "Modelo", "Empresa", "Lançamento", "Intelligence", "Coding", "Agentic", "Speed (tok/s)", "Custo/tarefa (US$)", "Input US$/1M", "Output US$/1M", "Open weights?", "Fonte abertura", "Versão índice"]
    current = [[(header, 1) for header in current_headers]]
    for position, row in enumerate(latest_rows, start=1):
        current.append([position, row["model_name"], row["model_creator"], row["release_date"], _number(row["intelligence_index"]), _number(row["coding_index"]), _number(row["agentic_index"]), _number(row["median_output_tokens_per_second"]), (_number(row["intelligence_index_cost_per_task_usd"]), 4), (_number(row["price_1m_input_tokens_usd"]), 4), (_number(row["price_1m_output_tokens_usd"]), 4), row.get("model_access_type", "Unknown"), row.get("access_classification_source", ""), row["intelligence_index_version"]])

    history_headers = ["Mês", "Coletado em UTC", "Campos alterados", "ID", "Slug", "Modelo", "Empresa", "Lançamento", "Tier", "Versão índice", "Intelligence", "Coding", "Agentic", "Speed (tok/s)", "TTFT (s)", "Custo/tarefa (US$)", "Input US$/1M", "Output US$/1M", "Open weights?", "Fonte abertura", "Modelo Epoch", "Acesso Epoch", "Fonte"]
    history = [[(header, 1) for header in history_headers]]
    for row in history_rows:
        history.append([row["reference_month"], row["collected_at_utc"], row.get("change_fields", ""), row["model_id"], row["model_slug"], row["model_name"], row["model_creator"], row["release_date"], row["api_tier"], row["intelligence_index_version"], _number(row["intelligence_index"]), _number(row["coding_index"]), _number(row["agentic_index"]), _number(row["median_output_tokens_per_second"]), _number(row["median_time_to_first_token_seconds"]), (_number(row["intelligence_index_cost_per_task_usd"]), 4), (_number(row["price_1m_input_tokens_usd"]), 4), (_number(row["price_1m_output_tokens_usd"]), 4), row.get("model_access_type", "Unknown"), row.get("access_classification_source", ""), row.get("epoch_model_name", ""), row.get("epoch_accessibility", ""), row["source_url"]])

    runs_headers = ["Execução", "Coletado em UTC", "Mês", "Modelos consultados", "Novos", "Alterados", "Sem mudança", "Tier API", "Versão índice", "Epoch AI"]
    runs = [[(header, 1) for header in runs_headers]]
    for row in run_rows:
        runs.append([row["run_id"], row["collected_at_utc"], row["reference_month"], _number(row["models_received"]), _number(row["new_models"]), _number(row["changed_models"]), _number(row["unchanged_models"]), row["api_tier"], row["intelligence_index_version"], row["epoch_access_status"]])

    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"Radar_IA_{run_id}.xlsx"
    content_types = '''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet4.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'''
    relationships = '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Visão geral" sheetId="1" r:id="rId1"/><sheet name="Última coleta" sheetId="2" r:id="rId2"/><sheet name="Histórico" sheetId="3" r:id="rId3"/><sheet name="Execuções" sheetId="4" r:id="rId4"/></sheets></workbook>'''
    workbook_relationships = '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/><Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet4.xml"/><Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_relationships)
        archive.writestr("xl/styles.xml", _styles())
        archive.writestr("xl/worksheets/sheet1.xml", _worksheet(overview, [31, 85, 12, 12, 12, 12], merge_title=True))
        archive.writestr("xl/worksheets/sheet2.xml", _worksheet(current, [10, 38, 20, 14, 14, 12, 12, 15, 18, 15, 16, 16, 20, 16], frozen=True))
        archive.writestr("xl/worksheets/sheet3.xml", _worksheet(history, [10, 22, 35, 38, 32, 42, 20, 14, 12, 14, 12, 12, 12, 15, 12, 18, 15, 16, 16, 18, 32, 20, 52], frozen=True))
        archive.writestr("xl/worksheets/sheet4.xml", _worksheet(runs, [24, 22, 10, 18, 10, 12, 14, 12, 14, 16], frozen=True))
    return output_path
