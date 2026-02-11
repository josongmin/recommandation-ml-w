"""Tests for feature parity checker."""

from wine_rec.features.parity_checker import check_parity
from wine_rec.schemas.manifest import FeatureTier


class TestCheckParity:
    def test_exact_float_match_passes(self):
        result = check_parity(
            feature_name="user_price_elasticity",
            tier=FeatureTier.CRITICAL,
            online_value=0.75,
            offline_value=0.75,
        )
        assert result.passed is True
        assert result.diff == 0.0

    def test_float_within_eps_passes(self):
        result = check_parity(
            feature_name="user_price_elasticity",
            tier=FeatureTier.CRITICAL,
            online_value=0.75,
            offline_value=0.75 + 1e-7,
        )
        assert result.passed is True

    def test_float_outside_eps_fails(self):
        result = check_parity(
            feature_name="user_price_elasticity",
            tier=FeatureTier.CRITICAL,
            online_value=0.75,
            offline_value=0.80,
        )
        assert result.passed is False

    def test_string_mismatch_fails(self):
        result = check_parity(
            feature_name="item_core_variety",
            tier=FeatureTier.IMPORTANT,
            online_value="cabernet",
            offline_value="merlot",
        )
        assert result.passed is False

    def test_experimental_always_passes(self):
        result = check_parity(
            feature_name="experimental_feat",
            tier=FeatureTier.EXPERIMENTAL,
            online_value=1.0,
            offline_value=99.0,
        )
        assert result.passed is True
