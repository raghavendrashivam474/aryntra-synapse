"""S12 - Tests for Priority Calibration Config and Matrix Generator."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.context.calibration import (
    PriorityCalibrationConfig,
    CalibrationMatrixGenerator,
)


class TestPriorityCalibrationConfig:
    def test_default_weights_valid(self):
        cfg = PriorityCalibrationConfig()
        assert cfg.validate()

    def test_custom_weights_valid(self):
        cfg = PriorityCalibrationConfig(0.4, 0.4, 0.2, label="test")
        assert cfg.validate()
        assert cfg.label == "test"

    def test_negative_weights_invalid(self):
        cfg = PriorityCalibrationConfig(-0.1, 0.6, 0.5)
        assert not cfg.validate()

    def test_to_weights_conversion(self):
        cfg = PriorityCalibrationConfig(0.6, 0.3, 0.1)
        w = cfg.to_weights()
        assert w.semantic_weight == 0.6
        assert w.lexical_weight == 0.3
        assert w.reuse_weight == 0.1

    def test_to_dict(self):
        cfg = PriorityCalibrationConfig(label="test_dict")
        d = cfg.to_dict()
        assert d["label"] == "test_dict"
        assert "semantic_weight" in d
        assert d["valid"] is True

    def test_zero_weights_valid(self):
        cfg = PriorityCalibrationConfig(0.0, 0.0, 0.0, label="all_zero")
        assert cfg.validate()


class TestCalibrationMatrixGenerator:
    def test_single_factor_count(self):
        configs = CalibrationMatrixGenerator.single_factor()
        assert len(configs) == 3

    def test_single_factor_labels(self):
        configs = CalibrationMatrixGenerator.single_factor()
        labels = {c.label for c in configs}
        assert "semantic_only" in labels
        assert "lexical_only" in labels
        assert "reuse_only" in labels

    def test_pairwise_count(self):
        configs = CalibrationMatrixGenerator.pairwise(steps=5)
        assert len(configs) > 0
        for c in configs:
            assert c.validate()

    def test_full_blend_count(self):
        configs = CalibrationMatrixGenerator.full_blend(steps=5)
        assert len(configs) > 0
        for c in configs:
            assert c.validate()

    def test_full_matrix_no_duplicates(self):
        matrix = CalibrationMatrixGenerator.full_matrix()
        labels = [c.label for c in matrix]
        assert len(labels) == len(set(labels))

    def test_full_matrix_all_valid(self):
        matrix = CalibrationMatrixGenerator.full_matrix()
        for c in matrix:
            assert c.validate(), f"Invalid config: {c.label}"

    def test_full_matrix_minimum_size(self):
        matrix = CalibrationMatrixGenerator.full_matrix()
        assert len(matrix) >= 15
