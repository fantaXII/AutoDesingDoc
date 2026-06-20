from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.config_loader import ThresholdConfig


class HysteresisDecision(Enum):
    CREATE = "create"
    UPDATE = "update"
    KEEP = "keep"
    DELETE = "delete"
    SKIP = "skip"


@dataclass
class FolderAction:
    folder_path: str
    decision: HysteresisDecision
    file_count: int
    doc_path: str
    child_doc_paths: list[str] = field(default_factory=list)
    child_folder_paths: list[str] = field(default_factory=list)
    parent_doc_path: str | None = None


class HysteresisEvaluator:
    def __init__(self, thresholds: ThresholdConfig):
        if thresholds.create <= thresholds.delete:
            raise ValueError(
                f"create 임계값({thresholds.create})은 delete 임계값({thresholds.delete})보다 커야 합니다"
            )
        self._thresholds = thresholds

    def decide(
        self,
        file_count: int,
        doc_exists: bool,
        has_structural_change: bool = True,
    ) -> HysteresisDecision:
        """
        결정 매트릭스:
          file_count >= create AND not doc_exists               → CREATE
          file_count >= create AND doc_exists AND change        → UPDATE
          file_count >= create AND doc_exists AND no change     → KEEP
          delete < file_count < create AND doc_exists AND change → UPDATE
          delete < file_count < create AND doc_exists AND !chg  → KEEP
          delete < file_count < create AND not doc_exists       → SKIP
          file_count <= delete AND doc_exists                   → DELETE
          file_count <= delete AND not doc_exists               → SKIP
        """
        create = self._thresholds.create
        delete = self._thresholds.delete

        if file_count <= delete:
            return HysteresisDecision.DELETE if doc_exists else HysteresisDecision.SKIP

        if file_count >= create:
            if not doc_exists:
                return HysteresisDecision.CREATE
            return HysteresisDecision.UPDATE if has_structural_change else HysteresisDecision.KEEP

        # delete < file_count < create (Hysteresis 구간)
        if not doc_exists:
            return HysteresisDecision.SKIP
        return HysteresisDecision.UPDATE if has_structural_change else HysteresisDecision.KEEP
