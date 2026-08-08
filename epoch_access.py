"""Classifica a disponibilidade de pesos a partir do dataset público da Epoch AI."""

import csv
import io
import re
import unicodedata
from urllib.request import Request, urlopen

EPOCH_MODELS_URL = "https://epoch.ai/data/all_ai_models.csv"


def _normalise(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _base_name(value: str) -> str:
    return _normalise(re.sub(r"\s*\([^)]*\)", "", value or ""))


def _access_type(row: dict) -> tuple[str, str]:
    open_weights = (row.get("Open model weights?") or "").strip().lower()
    accessibility = (row.get("Model accessibility") or "").strip()
    if open_weights in {"yes", "true", "y"} or "open weights" in accessibility.lower():
        return "Open weights", accessibility
    if open_weights in {"no", "false", "n"} or accessibility.lower() in {"api access", "hosted access", "unreleased"}:
        return "Proprietary", accessibility
    return "Unknown", accessibility


class EpochAccessIndex:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.by_name = {}
        self.by_base_name = {}
        for row in rows:
            name = row.get("Model") or ""
            if name:
                self.by_name.setdefault(_normalise(name), row)
                self.by_base_name.setdefault(_base_name(name), row)

    def classify(self, model_name: str) -> dict:
        key = _normalise(model_name)
        base_key = _base_name(model_name)
        match = self.by_name.get(key) or self.by_base_name.get(base_key)
        if not match:
            return {
                "model_access_type": "Unknown",
                "access_classification_source": "Epoch AI (no match)",
                "epoch_model_name": None,
                "epoch_accessibility": None,
            }
        access_type, accessibility = _access_type(match)
        return {
            "model_access_type": access_type,
            "access_classification_source": "Epoch AI",
            "epoch_model_name": match.get("Model"),
            "epoch_accessibility": accessibility or None,
        }


def fetch_epoch_access_index() -> tuple[EpochAccessIndex, str]:
    request = Request(EPOCH_MODELS_URL, headers={"Accept": "text/csv", "User-Agent": "Radar-IA/1.0"})
    with urlopen(request, timeout=60) as response:
        csv_text = response.read().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    if not rows or "Model" not in rows[0]:
        raise RuntimeError("CSV da Epoch AI não contém a coluna esperada 'Model'.")
    return EpochAccessIndex(rows), csv_text
