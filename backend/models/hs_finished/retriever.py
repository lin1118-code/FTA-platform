from pathlib import Path
import json
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
INPUT_COLUMNS = ["Product Name", "Main Ingredients (KR)", "Main Ingredients (EN)", "Product Form and Packaging", "Intended Use"]

class FinishedProductHSRetriever:
    def __init__(self, artifact_dir=ARTIFACT_DIR):
        artifact_dir = Path(artifact_dir)
        config_path = artifact_dir / "config.json"
        metadata_path = artifact_dir / "metadata.csv"
        embeddings_path = artifact_dir / "embeddings.npy"
        missing = [str(p) for p in [config_path, metadata_path, embeddings_path] if not p.exists()]
        if missing:
            raise FileNotFoundError(f"운영 인덱스 파일이 없습니다: {missing}. 먼저 build_index.py를 실행하세요.")
        self.config = json.loads(config_path.read_text(encoding="utf-8"))
        self.metadata = pd.read_csv(metadata_path, encoding="utf-8-sig").fillna("")
        self.embeddings = np.load(embeddings_path)
        if len(self.metadata) != len(self.embeddings):
            raise ValueError("metadata와 embeddings의 행 수가 일치하지 않습니다.")
        self.encoder = SentenceTransformer(self.config["model_name"])

    def predict(self, product, top_k=3):
        values = {col: str(product.get(col, "") or "").strip() for col in INPUT_COLUMNS}
        if not any(values.values()):
            raise ValueError("제품명, 성분, 형태·포장, 용도 중 하나 이상 입력해야 합니다.")
        query_text = " ".join(values[col] for col in INPUT_COLUMNS).strip()
        query_embedding = self.encoder.encode(["query: " + query_text], normalize_embeddings=True, convert_to_numpy=True)[0]
        scores = self.embeddings @ query_embedding
        order = np.argsort(scores)[::-1]
        candidates = []
        seen_codes = set()
        for idx in order:
            row = self.metadata.iloc[int(idx)]
            code = str(row[self.config["target_column"]])
            if code in seen_codes:
                continue
            seen_codes.add(code)
            candidates.append({"hs_code": code, "similarity": float(scores[idx]), "matched_case": {col: str(row.get(col, "")) for col in INPUT_COLUMNS}, "ruling_summary": str(row.get(self.config["summary_column"], ""))})
            if len(candidates) >= max(1, min(int(top_k), 10)):
                break
        return {"model": self.config["selected_variant"], "query": values, "top1": candidates[0] if candidates else None, "candidates": candidates, "retrieval_count": len(self.metadata), "notice": "과거 판정 사례 기반 예측 후보이며, 최종 HS 코드는 공식 품목분류 및 원산지 판정 확인이 필요합니다."}
