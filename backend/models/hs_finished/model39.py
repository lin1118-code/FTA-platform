"""Production inference wrapper for experiment 39.

This module intentionally contains no LOPO validation or hyperparameter search.
It loads the externally supplied source checkout, builds a reusable retrieval index,
and applies the operating configuration recorded from experiment 39.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


INPUT_COLUMNS = [
    "Product Name",
    "Main Ingredients (KR)",
    "Main Ingredients (EN)",
    "Product Form and Packaging",
    "Intended Use",
]
TARGET = "HS Code"
SUMMARY = "Preprocessed Ruling Summary"
MODEL_NAME = "intfloat/multilingual-e5-base"
E5_MODEL_DIR_ENV = "FTA_FINISHED_HS39_E5_MODEL_DIR"
SUPPORTED_HS4 = ("3304", "3305", "3306", "3307", "3401")
SUPPORTED_HS6 = (
    "330410", "330420", "330491", "330499", "330510", "330590",
    "330690", "330730", "330749", "330790", "340111",
)
OPERATING_CONFIG = {
    "product_aggregation": "top3_mean",
    "product_weight": 1.0,
    "ruling_aggregation": "top3_mean",
    "ruling_weight": 1.0,
    "direct_aggregation": "top3_mean",
    "exclusion_aggregation": "max",
    "direct_weight": 0.5,
    "exclusion_weight": 0.5,
    "rrf_k": 60,
}
EXPECTED_CASE_COUNT = 195


class Model39NotReady(RuntimeError):
    """The external source checkout, data, or operating dependency is unavailable."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_name(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).lower()
    return re.sub(r"[^0-9a-z가-힣]+", "", normalized)


def _read_cases(source_dir: Path) -> pd.DataFrame:
    old_path = _find_source_file(source_dir, lambda path: path.suffix == ".csv" and "177" in path.name, "기존 177건 사례 CSV")
    new_path = _find_source_file(source_dir, lambda path: path.suffix == ".csv" and path.name.startswith("CLIP_MTI227_"), "신규 89건 사례 CSV")
    frames = []
    for path, origin in ((old_path, "existing_177"), (new_path, "new_89")):
        frame = pd.read_csv(path, encoding="utf-8-sig").fillna("")
        for column in INPUT_COLUMNS + [TARGET, SUMMARY]:
            if column not in frame:
                frame[column] = ""
            frame[column] = frame[column].astype(str).str.strip()
        frame = frame[frame[TARGET].ne("")].copy()
        frame["data_source"] = origin
        frames.append(frame)
    cases = pd.concat(frames, ignore_index=True)
    cases["name_key"] = cases["Product Name"].map(_normalize_name)
    cases = cases[cases["name_key"].ne("")].drop_duplicates("name_key", keep="first").copy()
    cases["hs_digits"] = cases[TARGET].map(lambda value: re.sub(r"\D", "", str(value)))
    cases["hs6"] = cases["hs_digits"].str[:6]
    cases["hs4"] = cases["hs_digits"].str[:4]
    # The eligible HS6 labels are the frozen evaluation cohort from experiment 29/39.
    # Filtering only by HS4 would add 30 unsupported records and change the index.
    cases = cases[cases["hs6"].isin(SUPPORTED_HS6)].copy()
    cases["query_text"] = cases[INPUT_COLUMNS].agg(" ".join, axis=1).str.strip()
    cases["ruling_text"] = (cases["query_text"] + " " + cases[SUMMARY]).str.strip()
    cases = cases.reset_index(drop=True)
    if len(cases) != EXPECTED_CASE_COUNT:
        raise Model39NotReady(
            f"모델 39 운영 사례 수가 검증 데이터와 다릅니다: {len(cases)} (기대값 {EXPECTED_CASE_COUNT})"
        )
    return cases


def _find_source_file(source_dir: Path, predicate: Any, description: str) -> Path:
    matches = [path for path in source_dir.iterdir() if path.is_file() and predicate(path)]
    if len(matches) != 1:
        raise Model39NotReady(f"모델 39 {description}를 고유하게 찾을 수 없습니다: {matches}")
    return matches[0]


def _read_knowledge_base(source_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = source_dir / "hs_knowledge_base.jsonl"
    if not path.exists():
        raise Model39NotReady(f"모델 39 지식베이스가 없습니다: {path}")
    knowledge = pd.read_json(path, lines=True).fillna("")
    for column in ("knowledge_id", "hs_code", "rule_type", "document_text", "source_sheet", "source_page_or_line"):
        if column not in knowledge:
            knowledge[column] = ""
        knowledge[column] = knowledge[column].astype(str).str.strip()
    knowledge["hs_digits"] = knowledge["hs_code"].map(lambda value: re.sub(r"\D", "", value))
    knowledge["embedding_text"] = knowledge["document_text"].map(_clean_knowledge_text)

    direct_rows: list[dict[str, Any]] = []
    exclusion_rows: list[dict[str, Any]] = []
    for _, row in knowledge.iterrows():
        own_hs4 = row["hs_digits"][:4]
        rule_type = row["rule_type"]
        if own_hs4 in SUPPORTED_HS4 and row["embedding_text"] and "제외" not in rule_type:
            direct_rows.append({**row.to_dict(), "candidate_hs4": own_hs4, "channel": "direct"})
        if "제외" in rule_type and row["embedding_text"]:
            for hs4 in sorted(set(re.findall(r"(?:제\s*)?(\d{4})\s*호", row["document_text"]))):
                if hs4 in SUPPORTED_HS4:
                    exclusion_rows.append({**row.to_dict(), "candidate_hs4": hs4, "channel": "exclusion"})
    direct = pd.DataFrame(direct_rows).drop_duplicates(["knowledge_id", "candidate_hs4"]).reset_index(drop=True)
    exclusion = pd.DataFrame(exclusion_rows).drop_duplicates(["knowledge_id", "candidate_hs4"]).reset_index(drop=True)
    if direct.empty or exclusion.empty:
        raise Model39NotReady("모델 39 direct/exclusion 규칙 인덱스를 만들 수 없습니다.")
    return direct, exclusion


def _clean_knowledge_text(value: object) -> str:
    ignored = re.compile(r"^(규칙_ID|HS코드|자료출처|표|페이지번호)\s*:")
    return " ".join(line.strip() for line in str(value).splitlines() if line.strip() and not ignored.match(line.strip()))


def _aggregate_hs4(scores: np.ndarray, codes: np.ndarray, method: str) -> pd.Series:
    table = pd.DataFrame({"hs4": np.asarray(codes).astype(str), "score": np.asarray(scores, dtype=float)})
    if method == "max":
        values = table.groupby("hs4").score.max()
    elif method == "top3_mean":
        values = table.groupby("hs4").score.apply(lambda score: score.nlargest(min(3, len(score))).mean())
    else:
        raise ValueError(f"지원하지 않는 집계 방식: {method}")
    return values.reindex(SUPPORTED_HS4, fill_value=-1.0).sort_values(ascending=False)


def _rrf(ranks: list[pd.Series], weights: list[float], k: int = 60) -> pd.Series:
    positions = [{str(code): position + 1 for position, code in enumerate(rank.index)} for rank in ranks]
    values = {
        hs4: sum(weight / (k + position.get(hs4, 99999)) for weight, position in zip(weights, positions))
        for hs4 in SUPPORTED_HS4
    }
    return pd.Series(values, dtype=float).sort_values(ascending=False)


@dataclass
class _Index:
    cases: pd.DataFrame
    direct_docs: pd.DataFrame
    exclusion_docs: pd.DataFrame
    product_embeddings: np.ndarray
    ruling_embeddings: np.ndarray
    direct_embeddings: np.ndarray
    exclusion_embeddings: np.ndarray


class Model39Predictor:
    """Reusable index and fixed-setting inference for new product inputs."""

    def __init__(self, source_dir: str | Path, cache_dir: str | Path | None = None):
        self.source_dir = Path(source_dir).expanduser().resolve()
        if not self.source_dir.exists():
            raise Model39NotReady(f"FTA_FINISHED_HS39_SOURCE_DIR 경로가 없습니다: {self.source_dir}")
        configured_cache_dir = cache_dir or os.getenv("FTA_FINISHED_HS39_CACHE_DIR")
        self.cache_dir = (
            Path(configured_cache_dir).expanduser()
            if configured_cache_dir
            else Path(tempfile.gettempdir()) / "fta-platform" / "model39"
        )
        self._encoder: Any | None = None
        self._index: _Index | None = None

    @property
    def encoder(self):
        if self._encoder is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise Model39NotReady("sentence-transformers 의존성이 없어 모델 39를 실행할 수 없습니다.") from exc
            configured_path = os.getenv(E5_MODEL_DIR_ENV)
            if configured_path:
                local_path = Path(configured_path).expanduser().resolve()
                if not (local_path / "config.json").is_file():
                    raise Model39NotReady(
                        f"{E5_MODEL_DIR_ENV} does not contain config.json: {local_path}"
                    )
                if not any((local_path / name).is_file() for name in ("model.safetensors", "pytorch_model.bin")):
                    raise Model39NotReady(
                        f"{E5_MODEL_DIR_ENV} does not contain E5 weights: {local_path}"
                    )
                self._encoder = SentenceTransformer(str(local_path), local_files_only=True)
            else:
                self._encoder = SentenceTransformer(MODEL_NAME)
        return self._encoder

    def _encode_query(self, texts: list[str]) -> np.ndarray:
        return self.encoder.encode([f"query: {text}" for text in texts], batch_size=16, normalize_embeddings=True, convert_to_numpy=True)

    def _encode_passage(self, texts: list[str]) -> np.ndarray:
        return self.encoder.encode([f"passage: {text}" for text in texts], batch_size=16, normalize_embeddings=True, convert_to_numpy=True)

    def _cache_paths(self) -> tuple[Path, Path]:
        return self.cache_dir / "model39_index.npz", self.cache_dir / "model39_manifest.json"

    def _manifest(self, cases: pd.DataFrame, direct: pd.DataFrame, exclusion: pd.DataFrame) -> dict[str, Any]:
        tracked = [
            _find_source_file(self.source_dir, lambda path: path.suffix == ".csv" and "177" in path.name, "기존 177건 사례 CSV"),
            _find_source_file(self.source_dir, lambda path: path.suffix == ".csv" and path.name.startswith("CLIP_MTI227_"), "신규 89건 사례 CSV"),
            self.source_dir / "hs_knowledge_base.jsonl",
        ]
        return {
            "model_name": MODEL_NAME,
            "e5_model_config_sha256": self._e5_config_digest(),
            "source_commit": os.getenv("FTA_FINISHED_HS39_SOURCE_COMMIT", "7cb3107d448bc6ed3324944e75d951976766e994"),
            "source_files": {path.name: _sha256(path) for path in tracked},
            "case_count": len(cases),
            "direct_document_count": len(direct),
            "exclusion_document_count": len(exclusion),
            "supported_hs4": list(SUPPORTED_HS4),
            "supported_hs6": list(SUPPORTED_HS6),
            "operating_config": OPERATING_CONFIG,
        }

    @staticmethod
    def _e5_config_digest() -> str | None:
        configured_path = os.getenv(E5_MODEL_DIR_ENV)
        if not configured_path:
            return None
        config = Path(configured_path).expanduser() / "config.json"
        return _sha256(config) if config.is_file() else None

    def load(self) -> None:
        if self._index is not None:
            return
        cases = _read_cases(self.source_dir)
        direct, exclusion = _read_knowledge_base(self.source_dir)
        manifest = self._manifest(cases, direct, exclusion)
        index_path, manifest_path = self._cache_paths()
        try:
            saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if saved_manifest == manifest and index_path.exists():
                arrays = np.load(index_path)
                self._index = _Index(cases, direct, exclusion, arrays["product"], arrays["ruling"], arrays["direct"], arrays["exclusion"])
                return
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            pass

        product = self._encode_passage(cases["query_text"].tolist())
        ruling = self._encode_passage(cases["ruling_text"].tolist())
        direct_embeddings = self._encode_passage(direct["embedding_text"].tolist())
        exclusion_embeddings = self._encode_passage(exclusion["embedding_text"].tolist())
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(index_path, product=product, ruling=ruling, direct=direct_embeddings, exclusion=exclusion_embeddings)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self._index = _Index(cases, direct, exclusion, product, ruling, direct_embeddings, exclusion_embeddings)

    def predict(self, product: dict[str, str], top_k: int = 3) -> dict[str, Any]:
        values = {column: str(product.get(column, "") or "").strip() for column in INPUT_COLUMNS}
        if not any(values.values()):
            raise ValueError("제품명, 성분, 제형·포장, 용도 중 하나 이상을 입력해야 합니다.")
        self.load()
        assert self._index is not None
        query = self._encode_query([" ".join(values[column] for column in INPUT_COLUMNS).strip()])[0]
        index = self._index
        product_rank = _aggregate_hs4(index.product_embeddings @ query, index.cases["hs4"].to_numpy(), OPERATING_CONFIG["product_aggregation"])
        ruling_rank = _aggregate_hs4(index.ruling_embeddings @ query, index.cases["hs4"].to_numpy(), OPERATING_CONFIG["ruling_aggregation"])
        base_rank = _rrf(
            [product_rank, ruling_rank],
            [OPERATING_CONFIG["product_weight"], OPERATING_CONFIG["ruling_weight"]],
            OPERATING_CONFIG["rrf_k"],
        )
        direct_rank = _aggregate_hs4(index.direct_embeddings @ query, index.direct_docs["candidate_hs4"].to_numpy(), OPERATING_CONFIG["direct_aggregation"])
        exclusion_rank = _aggregate_hs4(index.exclusion_embeddings @ query, index.exclusion_docs["candidate_hs4"].to_numpy(), OPERATING_CONFIG["exclusion_aggregation"])
        final_rank = _rrf(
            [base_rank, direct_rank, exclusion_rank],
            [1.0, OPERATING_CONFIG["direct_weight"], OPERATING_CONFIG["exclusion_weight"]],
            OPERATING_CONFIG["rrf_k"],
        )
        candidates = [self._candidate(code, float(score), index, query) for code, score in final_rank.head(max(1, min(top_k, 3))).items()]
        return {
            "scope": {"supported_hs4": list(SUPPORTED_HS4), "classification": "HS4 candidate suggestion only"},
            "operating_config": OPERATING_CONFIG,
            "candidates": candidates,
            "top1": candidates[0] if candidates else None,
            "index": {"case_count": len(index.cases), "direct_document_count": len(index.direct_docs), "exclusion_document_count": len(index.exclusion_docs)},
            "validation": {
                "tuned_lopo_macro_f1": 0.7749290270658206,
                "tuned_lopo_accuracy": 0.8256410256410256,
                "fixed36_lopo_macro_f1": 0.7138095238095238,
                "fixed36_lopo_accuracy": 0.7948717948717948,
                "fixed36_selected_in_outer_folds": "28/29",
            },
        }

    def _candidate(self, hs4: str, rrf_score: float, index: _Index, query: np.ndarray) -> dict[str, Any]:
        cases = index.cases[index.cases["hs4"].eq(hs4)].copy()
        cases["similarity"] = np.maximum(index.product_embeddings @ query, index.ruling_embeddings @ query)[cases.index]
        case_rows = cases.nlargest(3, "similarity")
        direct = index.direct_docs[index.direct_docs["candidate_hs4"].eq(hs4)].copy()
        direct["similarity"] = (index.direct_embeddings @ query)[direct.index]
        exclusion = index.exclusion_docs[index.exclusion_docs["candidate_hs4"].eq(hs4)].copy()
        exclusion["similarity"] = (index.exclusion_embeddings @ query)[exclusion.index]
        def evidence(rows: pd.DataFrame, kind: str) -> list[dict[str, Any]]:
            return [
                {"type": kind, "similarity": float(row.similarity), "knowledge_id": str(getattr(row, "knowledge_id", "")), "rule_type": str(getattr(row, "rule_type", "")), "source": str(getattr(row, "source_page_or_line", "")), "text": str(getattr(row, "embedding_text", ""))}
                for row in rows.nlargest(3, "similarity").itertuples()
            ]
        return {
            "hs4": hs4,
            "rrf_score": rrf_score,
            "matched_cases": [
                {"product_name": str(row["Product Name"]), "hs_code": str(row[TARGET]), "similarity": float(row["similarity"]), "ruling_summary": str(row[SUMMARY])}
                for _, row in case_rows.iterrows()
            ],
            "direct_evidence": evidence(direct, "direct_explanatory_note"),
            "exclusion_evidence": evidence(exclusion, "exclusion_explanatory_note"),
        }
