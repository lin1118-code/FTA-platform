import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.schemas.platform import (
    AgreementRuleInput,
    BOMLineInput,
    BOMLineRecord,
    ProductInput,
    ProductRecord,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlatformRepository:
    """Small SQLite repository for product/BOM inputs, rules and analysis history."""

    def __init__(self, db_path: str | None = None):
        configured = db_path or os.getenv("FTA_PLATFORM_DB")
        self.db_path = Path(configured) if configured else Path("backend/data/fta_platform.sqlite3")

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bom_lines (
                    line_id TEXT PRIMARY KEY, product_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY(product_id) REFERENCES products(product_id)
                );
                CREATE TABLE IF NOT EXISTS agreement_rules (
                    rule_id TEXT PRIMARY KEY, agreement_code TEXT NOT NULL,
                    product_hs_code TEXT NOT NULL, effective_from TEXT NOT NULL,
                    effective_to TEXT, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id TEXT PRIMARY KEY, product_id TEXT NOT NULL,
                    status TEXT NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create_product(self, data: ProductInput) -> ProductRecord:
        now = _now()
        product_id = str(uuid4())
        payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
        with self._connection() as db:
            db.execute(
                "INSERT INTO products VALUES (?, ?, ?, ?)",
                (product_id, json.dumps(payload, ensure_ascii=False), now, now),
            )
        return ProductRecord(product_id=product_id, **payload, created_at=now, updated_at=now)

    def get_product(self, product_id: str) -> ProductRecord | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM products WHERE product_id=?", (product_id,)).fetchone()
        if row is None:
            return None
        return ProductRecord(
            product_id=row["product_id"], **json.loads(row["payload"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def list_products(self) -> list[ProductRecord]:
        with self._connection() as db:
            rows = db.execute("SELECT * FROM products ORDER BY updated_at DESC").fetchall()
        return [ProductRecord(
            product_id=row["product_id"], **json.loads(row["payload"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        ) for row in rows]

    def update_product(self, product_id: str, data: ProductInput) -> ProductRecord | None:
        existing = self.get_product(product_id)
        if existing is None:
            return None
        now = _now()
        payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
        with self._connection() as db:
            db.execute(
                "UPDATE products SET payload=?, updated_at=? WHERE product_id=?",
                (json.dumps(payload, ensure_ascii=False), now, product_id),
            )
        return ProductRecord(
            product_id=product_id,
            **payload,
            created_at=existing.created_at,
            updated_at=now,
        )

    def replace_bom(self, product_id: str, lines: list[BOMLineInput]) -> list[BOMLineRecord] | None:
        if self.get_product(product_id) is None:
            return None
        records = []
        with self._connection() as db:
            db.execute("DELETE FROM bom_lines WHERE product_id=?", (product_id,))
            for line in lines:
                payload = line.model_dump() if hasattr(line, "model_dump") else line.dict()
                line_id = str(uuid4())
                db.execute(
                    "INSERT INTO bom_lines VALUES (?, ?, ?)",
                    (line_id, product_id, json.dumps(payload, ensure_ascii=False)),
                )
                records.append(BOMLineRecord(line_id=line_id, product_id=product_id, **payload))
        return records

    def get_bom(self, product_id: str) -> list[BOMLineRecord]:
        with self._connection() as db:
            rows = db.execute("SELECT * FROM bom_lines WHERE product_id=?", (product_id,)).fetchall()
        return [
            BOMLineRecord(line_id=row["line_id"], product_id=product_id, **json.loads(row["payload"]))
            for row in rows
        ]

    def save_rule(self, rule: AgreementRuleInput) -> dict[str, Any]:
        payload = rule.model_dump(mode="json") if hasattr(rule, "model_dump") else rule.dict()
        payload = json.loads(json.dumps(payload, default=str))
        payload["verified"] = False
        rule_id = str(uuid4())
        with self._connection() as db:
            db.execute(
                "INSERT INTO agreement_rules VALUES (?, ?, ?, ?, ?, ?)",
                (rule_id, rule.agreement_code, rule.product_hs_code, str(rule.effective_from),
                 str(rule.effective_to) if rule.effective_to else None,
                 json.dumps(payload, ensure_ascii=False)),
            )
        return {"rule_id": rule_id, **payload}

    def find_rule(self, agreement: str, hs_code: str, as_of: date) -> dict[str, Any] | None:
        with self._connection() as db:
            rows = db.execute(
                """SELECT payload FROM agreement_rules
                   WHERE agreement_code=? AND product_hs_code=? AND effective_from<=?
                   AND (effective_to IS NULL OR effective_to>=?)
                   ORDER BY effective_from DESC""",
                (agreement, hs_code, str(as_of), str(as_of)),
            ).fetchall()
        return json.loads(rows[0]["payload"]) if rows else None

    def list_rules(self, agreement: str, hs_code: str, as_of: date) -> list[dict[str, Any]]:
        with self._connection() as db:
            rows = db.execute(
                """SELECT rule_id, payload FROM agreement_rules
                   WHERE agreement_code=? AND product_hs_code=? AND effective_from<=?
                   AND (effective_to IS NULL OR effective_to>=?)
                   ORDER BY effective_from DESC""",
                (agreement, hs_code, str(as_of), str(as_of)),
            ).fetchall()
        return [{"rule_id": row["rule_id"], **json.loads(row["payload"])} for row in rows]

    def save_analysis(self, analysis_id: str, product_id: str, status: str, payload: dict[str, Any]) -> None:
        with self._connection() as db:
            db.execute(
                "INSERT INTO analyses VALUES (?, ?, ?, ?, ?)",
                (analysis_id, product_id, status, json.dumps(payload, ensure_ascii=False, default=str), _now()),
            )

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM analyses WHERE analysis_id=?", (analysis_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_analyses(self, product_id: str) -> list[dict[str, Any]]:
        with self._connection() as db:
            rows = db.execute(
                "SELECT payload FROM analyses WHERE product_id=? ORDER BY created_at DESC",
                (product_id,),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]
