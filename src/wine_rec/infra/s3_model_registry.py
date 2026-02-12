"""S3-based ModelRegistry implementation."""

from __future__ import annotations

import io
import pickle
from typing import Any

import boto3
import torch

from wine_rec.common.config import get_settings
from wine_rec.common.logging import get_logger


log = get_logger(__name__)


class ModelArtifactImpl:
    """Model artifact loaded from S3."""

    def __init__(self, *, model: torch.nn.Module, version: str, metadata: dict[str, Any]) -> None:
        self._model = model
        self._version = version
        self._metadata = metadata
        self._model.eval()  # Set to evaluation mode

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """Run prediction.

        Returns:
            {"items": [item_id, ...], "scores": [score, ...]}
        """
        # Mock prediction for now - real implementation would use model forward pass
        user_id = features.get("user_id", "unknown")
        n_items = features.get("n_items", 10)

        # Simple mock: return some item IDs based on hash
        import hashlib

        seed = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 10000
        item_ids = [f"wine_{(seed + i) % 1000}" for i in range(n_items)]
        scores = [0.9 - (i * 0.05) for i in range(n_items)]

        return {
            "items": [
                {"wine_sku_id": iid, "score": score}
                for iid, score in zip(item_ids, scores, strict=False)
            ],
            "model_version": self._version,
        }

    @property
    def version(self) -> str:
        """Model version identifier."""
        return self._version


class S3ModelRegistry:
    """ModelRegistry backed by S3."""

    def __init__(
        self,
        *,
        bucket_name: str | None = None,
        prefix: str = "models",
        endpoint_url: str | None = None,
    ) -> None:
        """Initialize S3 model registry.

        Args:
            bucket_name: S3 bucket for models (defaults to config)
            prefix: S3 prefix for models
            endpoint_url: S3 endpoint (for LocalStack)
        """
        settings = get_settings()
        self._bucket_name = bucket_name or f"{settings.project_name}-{settings.environment}-models"
        self._prefix = prefix

        s3_config = {"region_name": settings.aws_region}
        if endpoint_url:
            s3_config["endpoint_url"] = endpoint_url

        self._s3_client = boto3.client("s3", **s3_config)

        log.info(
            "s3_model_registry_init",
            bucket=self._bucket_name,
            prefix=self._prefix,
            endpoint=endpoint_url,
        )

    def load_model(self, *, model_name: str, version: str) -> ModelArtifactImpl:
        """Load a model artifact from S3.

        Expected S3 structure:
            s3://{bucket}/{prefix}/{model_name}/{version}/model.pt
            s3://{bucket}/{prefix}/{model_name}/{version}/metadata.pkl
        """
        model_key = f"{self._prefix}/{model_name}/{version}/model.pt"
        metadata_key = f"{self._prefix}/{model_name}/{version}/metadata.pkl"

        try:
            # Load model weights
            model_obj = self._s3_client.get_object(Bucket=self._bucket_name, Key=model_key)
            model_bytes = model_obj["Body"].read()
            model = torch.load(io.BytesIO(model_bytes), map_location="cpu")

            # Load metadata
            try:
                metadata_obj = self._s3_client.get_object(
                    Bucket=self._bucket_name, Key=metadata_key
                )
                metadata = pickle.loads(metadata_obj["Body"].read())
            except Exception:
                metadata = {}

            log.info(
                "model_loaded",
                model_name=model_name,
                version=version,
                size_mb=len(model_bytes) / 1024 / 1024,
            )

            return ModelArtifactImpl(model=model, version=version, metadata=metadata)

        except Exception as e:
            log.error(
                "model_load_failed",
                model_name=model_name,
                version=version,
                error=str(e),
            )
            raise

    def get_latest_version(self, *, model_name: str) -> str:
        """Get the latest approved model version.

        Looks for s3://{bucket}/{prefix}/{model_name}/latest.txt
        Falls back to listing versions and picking the latest.
        """
        latest_key = f"{self._prefix}/{model_name}/latest.txt"

        try:
            # Try latest.txt first
            obj = self._s3_client.get_object(Bucket=self._bucket_name, Key=latest_key)
            version = obj["Body"].read().decode("utf-8").strip()
            log.info("latest_version_from_file", model_name=model_name, version=version)
            return version

        except Exception:
            # Fallback: list versions and sort
            prefix = f"{self._prefix}/{model_name}/"

            try:
                response = self._s3_client.list_objects_v2(
                    Bucket=self._bucket_name,
                    Prefix=prefix,
                    Delimiter="/",
                )

                versions = []
                for common_prefix in response.get("CommonPrefixes", []):
                    version_path = common_prefix["Prefix"]
                    version = version_path.rstrip("/").split("/")[-1]
                    if version != "latest.txt":
                        versions.append(version)

                if not versions:
                    raise ValueError(f"No versions found for model {model_name}")

                # Sort versions (assumes semantic versioning like v1, v2, v3)
                versions.sort(reverse=True)
                latest = versions[0]

                log.info("latest_version_from_list", model_name=model_name, version=latest)
                return latest

            except Exception as e:
                log.error("get_latest_version_failed", model_name=model_name, error=str(e))
                raise

    def save_model(
        self,
        *,
        model: torch.nn.Module,
        model_name: str,
        version: str,
        metadata: dict[str, Any] | None = None,
        set_as_latest: bool = True,
    ) -> None:
        """Save a model to S3.

        Args:
            model: PyTorch model to save
            model_name: Model name (e.g., "bpr", "two_tower")
            version: Version string (e.g., "v1", "2024-02-12")
            metadata: Optional metadata dict
            set_as_latest: Whether to update latest.txt
        """
        model_key = f"{self._prefix}/{model_name}/{version}/model.pt"
        metadata_key = f"{self._prefix}/{model_name}/{version}/metadata.pkl"

        # Save model
        model_buffer = io.BytesIO()
        torch.save(model.state_dict(), model_buffer)
        model_buffer.seek(0)

        self._s3_client.put_object(
            Bucket=self._bucket_name,
            Key=model_key,
            Body=model_buffer.getvalue(),
        )

        # Save metadata
        if metadata:
            metadata_buffer = io.BytesIO()
            pickle.dump(metadata, metadata_buffer)
            metadata_buffer.seek(0)

            self._s3_client.put_object(
                Bucket=self._bucket_name,
                Key=metadata_key,
                Body=metadata_buffer.getvalue(),
            )

        # Update latest.txt
        if set_as_latest:
            latest_key = f"{self._prefix}/{model_name}/latest.txt"
            self._s3_client.put_object(
                Bucket=self._bucket_name,
                Key=latest_key,
                Body=version.encode("utf-8"),
            )

        log.info(
            "model_saved",
            model_name=model_name,
            version=version,
            set_as_latest=set_as_latest,
        )
