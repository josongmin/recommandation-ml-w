"""Tests for S3ModelRegistry."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, Mock, patch

import torch.nn as nn

from wine_rec.infra.s3_model_registry import ModelArtifactImpl, S3ModelRegistry


class DummyModel(nn.Module):
    """Dummy model for testing."""

    def __init__(self) -> None:
        super().__init__()
        self.fc = nn.Linear(10, 5)


class TestModelArtifactImpl:
    """Tests for ModelArtifactImpl."""

    def test_predict_returns_items(self) -> None:
        """Test predict returns items."""
        model = DummyModel()
        artifact = ModelArtifactImpl(model=model, version="v1", metadata={})

        result = artifact.predict({"user_id": "test_user", "n_items": 5})

        assert "items" in result
        assert len(result["items"]) == 5
        assert all("wine_sku_id" in item for item in result["items"])
        assert all("score" in item for item in result["items"])

    def test_version_property(self) -> None:
        """Test version property."""
        model = DummyModel()
        artifact = ModelArtifactImpl(model=model, version="v2", metadata={})

        assert artifact.version == "v2"


class TestS3ModelRegistry:
    """Tests for S3ModelRegistry."""

    @patch("wine_rec.infra.s3_model_registry.boto3")
    def test_init(self, mock_boto3: Mock) -> None:
        """Test initialization."""
        registry = S3ModelRegistry(
            bucket_name="test-bucket",
            prefix="models",
            endpoint_url="http://localhost:4566",
        )

        assert registry._bucket_name == "test-bucket"
        assert registry._prefix == "models"
        mock_boto3.client.assert_called_once()

    @patch("wine_rec.infra.s3_model_registry.boto3")
    def test_save_model(self, mock_boto3: Mock) -> None:
        """Test saving model to S3."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        registry = S3ModelRegistry(bucket_name="test-bucket")
        model = DummyModel()

        registry.save_model(
            model=model,
            model_name="test_model",
            version="v1",
            metadata={"key": "value"},
            set_as_latest=True,
        )

        # Should call put_object for model, metadata, and latest.txt
        assert mock_s3.put_object.call_count == 3

    @patch("wine_rec.infra.s3_model_registry.boto3")
    def test_get_latest_version_from_file(self, mock_boto3: Mock) -> None:
        """Test getting latest version from latest.txt."""
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": io.BytesIO(b"v3"),
        }
        mock_boto3.client.return_value = mock_s3

        registry = S3ModelRegistry(bucket_name="test-bucket")
        version = registry.get_latest_version(model_name="test_model")

        assert version == "v3"

    @patch("wine_rec.infra.s3_model_registry.boto3")
    @patch("wine_rec.infra.s3_model_registry.torch")
    def test_load_model(self, mock_torch: Mock, mock_boto3: Mock) -> None:
        """Test loading model from S3."""
        # Mock S3 responses
        mock_s3 = MagicMock()
        mock_model_data = b"fake_model_data"
        # pickled {"key": "value"}
        mock_metadata_data = (
            b"\x80\x04\x95\x0e\x00\x00\x00\x00\x00\x00\x00}\x94\x8c\x03key\x94\x8c\x05value\x94s."
        )

        mock_s3.get_object.side_effect = [
            {"Body": io.BytesIO(mock_model_data)},
            {"Body": io.BytesIO(mock_metadata_data)},
        ]
        mock_boto3.client.return_value = mock_s3

        # Mock torch.load
        mock_model = DummyModel()
        mock_torch.load.return_value = mock_model

        registry = S3ModelRegistry(bucket_name="test-bucket")
        artifact = registry.load_model(model_name="test_model", version="v1")

        assert artifact.version == "v1"
        mock_torch.load.assert_called_once()

    @patch("wine_rec.infra.s3_model_registry.boto3")
    def test_get_latest_version_from_list(self, mock_boto3: Mock) -> None:
        """Test getting latest version from listing when latest.txt doesn't exist."""
        mock_s3 = MagicMock()

        # First call (latest.txt) fails
        mock_s3.get_object.side_effect = Exception("Not found")

        # Second call (list_objects_v2) returns versions
        mock_s3.list_objects_v2.return_value = {
            "CommonPrefixes": [
                {"Prefix": "models/test_model/v1/"},
                {"Prefix": "models/test_model/v2/"},
                {"Prefix": "models/test_model/v3/"},
            ],
        }
        mock_boto3.client.return_value = mock_s3

        registry = S3ModelRegistry(bucket_name="test-bucket")
        version = registry.get_latest_version(model_name="test_model")

        # Should return latest (sorted reverse)
        assert version == "v3"
