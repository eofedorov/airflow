"""Валидация схем: валидные примеры проходят, невалидные — падают."""
import pytest
from pydantic import ValidationError

from app.contracts.schemas import ClassifyV1Out, Entity, ExtractV1Out


class TestClassifyV1Out:
    def test_valid_passes(self):
        data = {"label": "bug", "confidence": 0.93, "rationale": "Ошибка на странице оплаты."}
        out = ClassifyV1Out.model_validate(data)
        assert out.label == "bug"
        assert out.confidence == 0.93
        assert out.rationale == "Ошибка на странице оплаты."

    def test_valid_all_labels(self):
        for label in ("bug", "feature", "question", "other"):
            data = {"label": label, "confidence": 0.5, "rationale": "x"}
            assert ClassifyV1Out.model_validate(data).label == label

    def test_extra_field_forbidden(self):
        data = {"label": "bug", "confidence": 0.9, "rationale": "x", "extra": "no"}
        with pytest.raises(ValidationError) as exc:
            ClassifyV1Out.model_validate(data)
        assert "extra" in str(exc.value).lower() or "forbid" in str(exc.value).lower()

    def test_invalid_label_fails(self):
        data = {"label": "invalid_type", "confidence": 0.9, "rationale": "x"}
        with pytest.raises(ValidationError):
            ClassifyV1Out.model_validate(data)

    def test_confidence_out_of_range_fails(self):
        data = {"label": "bug", "confidence": 1.5, "rationale": "x"}
        with pytest.raises(ValidationError):
            ClassifyV1Out.model_validate(data)
        data = {"label": "bug", "confidence": -0.1, "rationale": "x"}
        with pytest.raises(ValidationError):
            ClassifyV1Out.model_validate(data)

    def test_wrong_type_fails(self):
        data = {"label": "bug", "confidence": "high", "rationale": "x"}
        with pytest.raises(ValidationError):
            ClassifyV1Out.model_validate(data)


class TestExtractV1Out:
    def test_valid_passes(self):
        data = {
            "entities": [{"type": "component", "value": "checkout"}, {"type": "version", "value": "2.1.3"}],
            "summary": "Ошибка оплаты после релиза 2.1.3.",
        }
        out = ExtractV1Out.model_validate(data)
        assert len(out.entities) == 2
        assert out.entities[0].type == "component"
        assert out.entities[0].value == "checkout"
        assert out.summary == "Ошибка оплаты после релиза 2.1.3."

    def test_extra_field_forbidden(self):
        data = {"entities": [], "summary": "x", "extra": 1}
        with pytest.raises(ValidationError) as exc:
            ExtractV1Out.model_validate(data)
        assert "extra" in str(exc.value).lower() or "forbid" in str(exc.value).lower()

    def test_entity_extra_forbidden(self):
        data = {"entities": [{"type": "a", "value": "b", "extra": "c"}], "summary": "x"}
        with pytest.raises(ValidationError):
            ExtractV1Out.model_validate(data)

    def test_summary_over_max_length_fails(self):
        data = {"entities": [], "summary": "x" * 2001}
        with pytest.raises(ValidationError):
            ExtractV1Out.model_validate(data)

    def test_valid_summary_at_max_length(self):
        data = {"entities": [], "summary": "x" * 2000}
        out = ExtractV1Out.model_validate(data)
        assert len(out.summary) == 2000
