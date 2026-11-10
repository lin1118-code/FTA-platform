from pathlib import Path
from urllib.parse import quote
import json
import numpy as np
import pandas as pd
from kiwipiepy import Kiwi
from sentence_transformers import SentenceTransformer

BASE_URL = "https://raw.githubusercontent.com/lin1118-code/HS-complete-product/main/"
DATA_FILE = "완제품 모델 데이터_사례_전처리 후 - 사례_전처리 완료.csv"
INPUT_COLUMNS = ["Product Name", "Main Ingredients (KR)", "Main Ingredients (EN)", "Product Form and Packaging", "Intended Use"]
TARGET = "HS Code"
SUMMARY = "Preprocessed Ruling Summary"
MODEL_NAME = "intfloat/multilingual-e5-base"
STOPWORDS = {"것", "경우", "관세율표", "규정", "기재", "등", "따라서", "물품", "및", "본건", "본품", "분류", "설명", "소호", "수", "이상", "제품", "함", "해당", "호", "표", "관세"}
OUTPUT_DIR = Path(__file__).resolve().parent / "artifacts"

def remove_stopword_morphs(text, kiwi):
    text = str(text)
    chars = list(text)
    for token in kiwi.tokenize(text):
        if token.form in STOPWORDS:
            for i in range(token.start, token.start + token.len):
                chars[i] = ""
    return "".join(chars)

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(BASE_URL + quote(DATA_FILE, safe=""), encoding="utf-8-sig").fillna("")
    required = INPUT_COLUMNS + [TARGET, SUMMARY]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {missing}")
    for col in required:
        df[col] = df[col].astype(str).str.strip()
    df = df[df[TARGET].ne("")].reset_index(drop=True)
    df["query_text"] = df[INPUT_COLUMNS].agg(" ".join, axis=1).str.strip()
    kiwi = Kiwi()
    df["ruling_sw"] = df[SUMMARY].map(lambda x: remove_stopword_morphs(x, kiwi))
    df["document_text"] = (df["query_text"] + " " + df["ruling_sw"]).str.strip()
    encoder = SentenceTransformer(MODEL_NAME)
    embeddings = encoder.encode(["passage: " + x for x in df["document_text"]], batch_size=32, show_progress_bar=True, normalize_embeddings=True, convert_to_numpy=True)
    metadata_columns = INPUT_COLUMNS + [TARGET, SUMMARY, "query_text", "ruling_sw", "document_text"]
    df[metadata_columns].to_csv(OUTPUT_DIR / "metadata.csv", index=False, encoding="utf-8-sig")
    np.save(OUTPUT_DIR / "embeddings.npy", embeddings)
    config = {"model_name": MODEL_NAME, "selected_variant": "SBERT_product_plus_ruling_stopword", "input_columns": INPUT_COLUMNS, "target_column": TARGET, "summary_column": SUMMARY, "stopwords": sorted(STOPWORDS), "row_count": len(df), "embedding_dimension": int(embeddings.shape[1]), "normalization": "L2", "document_prefix": "passage: ", "query_prefix": "query: "}
    (OUTPUT_DIR / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"운영 인덱스 생성 완료: {len(df)}건 / {embeddings.shape[1]}차원")
    print(f"저장 위치: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
