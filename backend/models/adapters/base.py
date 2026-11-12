from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from backend.schemas.platform import (
    IntegrationStatus,
    ModelMetadata,
    ModelRunResult,
    ModelSource,
    RunStatus,
)


class ModelAdapter(ABC):
    module: str
    metadata: ModelMetadata
    input_schema: type[BaseModel]

    def run(self, payload: dict[str, Any]) -> ModelRunResult:
        started = datetime.now(timezone.utc)
        try:
            if hasattr(self.input_schema, "model_validate"):
                validated = self.input_schema.model_validate(payload)
            else:  # Pydantic v1 compatibility
                validated = self.input_schema.parse_obj(payload)
        except Exception as exc:
            return ModelRunResult(
                module=self.module,
                status=RunStatus.FAILED,
                model=self.metadata,
                model_name=self.metadata.name,
                model_version=self.metadata.version,
                warnings=[f"입력 검증 실패: {exc}"],
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                timestamp=datetime.now(timezone.utc),
            )
        try:
            result, evidence, warnings = self.execute(validated)
            return ModelRunResult(
                module=self.module,
                status=RunStatus.SUCCEEDED,
                source=self.source,
                model=self.metadata,
                model_name=self.metadata.name,
                model_version=self.metadata.version,
                input_summary=self.summarize(validated),
                result=result,
                evidence=evidence,
                warnings=warnings,
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                timestamp=datetime.now(timezone.utc),
            )
        except AdapterNotConnected as exc:
            return ModelRunResult(
                module=self.module,
                status=RunStatus.NOT_CONNECTED,
                model=self.metadata,
                model_name=self.metadata.name,
                model_version=self.metadata.version,
                input_summary=self.summarize(validated),
                warnings=[str(exc)],
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as exc:
            return ModelRunResult(
                module=self.module,
                status=RunStatus.FAILED,
                model=self.metadata,
                model_name=self.metadata.name,
                model_version=self.metadata.version,
                input_summary=self.summarize(validated),
                warnings=[f"모델 실행 실패: {exc}"],
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                timestamp=datetime.now(timezone.utc),
            )

    @property
    def source(self) -> ModelSource:
        if self.metadata.integration_status == IntegrationStatus.MOCK:
            return ModelSource.MOCK
        return ModelSource.REAL_MODEL

    def summarize(self, value: BaseModel) -> dict[str, Any]:
        data = value.model_dump() if hasattr(value, "model_dump") else value.dict()
        return data

    @abstractmethod
    def execute(self, payload: BaseModel) -> tuple[dict[str, Any], list[Any], list[str]]:
        raise NotImplementedError


class AdapterNotConnected(RuntimeError):
    """Raised when a registered module has no verified executable model."""


class UnavailableAdapter(ModelAdapter):
    def __init__(self, module: str, name: str, input_schema: type[BaseModel]):
        self.module = module
        self.input_schema = input_schema
        self.metadata = ModelMetadata(
            name=name,
            integration_status=IntegrationStatus.PENDING,
        )

    def execute(self, payload: BaseModel) -> tuple[dict[str, Any], list[Any], list[str]]:
        raise AdapterNotConnected("실제 모델 저장소와 입력·출력 스키마 확인 전까지 미연결 상태입니다.")

