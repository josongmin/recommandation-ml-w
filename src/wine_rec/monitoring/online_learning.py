"""Online learning infrastructure for real-time model updates.

Industry SOTA (LinkedIn/Twitter):
- FTRL-Proximal (Follow-The-Regularized-Leader)
- Mini-batch gradient descent (streaming updates)
- Feature warmup (stabilize new features before full deployment)
- Delayed feedback handling (purchased items may take days to ship)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

from wine_rec.common.logging import get_logger


if TYPE_CHECKING:
    from numpy.typing import NDArray


log = get_logger(__name__)


@dataclass
class OnlineExample:
    """Single training example for online learning."""

    features: dict[str, float]
    label: float
    weight: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    propensity: float = 1.0


@dataclass
class FTRLState:
    """FTRL-Proximal optimizer state.

    Papers:
    - McMahan et al., "Ad Click Prediction: a View from the Trenches" (KDD 2013)
    - Used in production at Google, LinkedIn, Twitter
    """

    n_features: int
    z: NDArray[np.float64]  # Accumulated gradients
    n: NDArray[np.float64]  # Accumulated squared gradients
    w: NDArray[np.float64]  # Current weights


class FTRLProximal:
    """FTRL-Proximal online learning optimizer.

    Production advantages:
    - Memory efficient: O(d) storage for d features
    - L1 regularization → sparse weights
    - Adaptive learning rate per feature
    - Handles delayed feedback (IPS weighting)
    """

    def __init__(
        self,
        *,
        n_features: int,
        alpha: float = 0.1,
        beta: float = 1.0,
        lambda1: float = 1.0,
        lambda2: float = 1.0,
    ) -> None:
        """Initialize FTRL optimizer.

        Args:
            n_features: Number of features (embedding dim)
            alpha: Learning rate multiplier
            beta: Learning rate decay
            lambda1: L1 regularization (sparsity)
            lambda2: L2 regularization (stability)
        """
        self.n_features = n_features
        self.alpha = alpha
        self.beta = beta
        self.lambda1 = lambda1
        self.lambda2 = lambda2

        # Initialize state
        self.z = np.zeros(n_features, dtype=np.float64)
        self.n = np.zeros(n_features, dtype=np.float64)
        self.w = np.zeros(n_features, dtype=np.float64)

        log.info(
            "ftrl_init",
            n_features=n_features,
            alpha=alpha,
            beta=beta,
            lambda1=lambda1,
            lambda2=lambda2,
        )

    def update(
        self,
        *,
        features: NDArray[np.float64],
        gradient: NDArray[np.float64],
    ) -> None:
        """Update weights with new gradient.

        Args:
            features: Feature vector (sparse or dense)
            gradient: Gradient w.r.t. weights
        """
        # Update accumulated gradients
        self.z += (
            gradient - ((np.sqrt(self.n + gradient**2) - np.sqrt(self.n)) / self.alpha) * self.w
        )
        self.n += gradient**2

        # Recompute weights (closed-form from FTRL)
        for i in range(self.n_features):
            if abs(self.z[i]) <= self.lambda1:
                self.w[i] = 0.0
            else:
                sign_z = 1.0 if self.z[i] > 0 else -1.0
                self.w[i] = -(sign_z * self.lambda1 - self.z[i]) / (
                    (self.beta + np.sqrt(self.n[i])) / self.alpha + self.lambda2
                )

    def predict(self, *, features: NDArray[np.float64]) -> float:
        """Predict score for feature vector.

        Args:
            features: Feature vector

        Returns:
            Predicted score (logits)
        """
        return float(np.dot(self.w, features))

    def get_state(self) -> FTRLState:
        """Get current optimizer state (for checkpointing)."""
        return FTRLState(
            n_features=self.n_features,
            z=self.z.copy(),
            n=self.n.copy(),
            w=self.w.copy(),
        )

    def load_state(self, state: FTRLState) -> None:
        """Load optimizer state from checkpoint."""
        if state.n_features != self.n_features:
            msg = f"Feature dimension mismatch: {state.n_features} != {self.n_features}"
            raise ValueError(msg)

        self.z = state.z.copy()
        self.n = state.n.copy()
        self.w = state.w.copy()

        log.info("ftrl_state_loaded", n_features=self.n_features)


class MiniBatchOnlineLearner:
    """Mini-batch online learning with streaming updates.

    Production workflow:
    1. Collect feedback events (clicks, purchases) in real-time
    2. Buffer mini-batches (size=100-1000)
    3. Update model every 10 minutes
    4. Checkpoint every 1 hour to S3
    5. A/B test online vs batch model
    """

    def __init__(
        self,
        *,
        optimizer: FTRLProximal,
        batch_size: int = 100,
        update_interval_sec: int = 600,
    ) -> None:
        """Initialize mini-batch learner.

        Args:
            optimizer: FTRL optimizer
            batch_size: Mini-batch size for gradient updates
            update_interval_sec: Minimum time between updates
        """
        self.optimizer = optimizer
        self.batch_size = batch_size
        self.update_interval_sec = update_interval_sec

        self._buffer: list[OnlineExample] = []
        self._last_update: datetime = datetime.now()
        self._n_updates = 0

        log.info(
            "mini_batch_learner_init",
            batch_size=batch_size,
            update_interval_sec=update_interval_sec,
        )

    def add_example(self, example: OnlineExample) -> bool:
        """Add example to buffer and trigger update if ready.

        Args:
            example: Training example with features, label, weight

        Returns:
            True if model was updated, False otherwise
        """
        self._buffer.append(example)

        # Check if update conditions met
        time_elapsed = (datetime.now() - self._last_update).total_seconds()
        if len(self._buffer) >= self.batch_size and time_elapsed >= self.update_interval_sec:
            self._update_model()
            return True

        return False

    def _update_model(self) -> None:
        """Update model with buffered examples."""
        if not self._buffer:
            return

        log.info("online_update_start", n_examples=len(self._buffer))

        # Convert examples to arrays
        n_examples = len(self._buffer)
        n_features = self.optimizer.n_features

        X = np.zeros((n_examples, n_features), dtype=np.float64)
        y = np.zeros(n_examples, dtype=np.float64)
        weights = np.zeros(n_examples, dtype=np.float64)

        for i, example in enumerate(self._buffer):
            # Convert feature dict to dense vector (simplified)
            for feature_name, value in example.features.items():
                # Hash feature name to index (production uses feature hashing)
                feature_idx = hash(feature_name) % n_features
                X[i, feature_idx] = value

            y[i] = example.label
            weights[i] = example.weight / example.propensity  # IPS weighting

        # Compute gradients (logistic regression loss)
        for i in range(n_examples):
            pred = self.optimizer.predict(features=X[i])
            prob = 1.0 / (1.0 + np.exp(-pred))  # Sigmoid
            gradient = (prob - y[i]) * X[i] * weights[i]

            self.optimizer.update(features=X[i], gradient=gradient)

        # Clear buffer
        self._buffer.clear()
        self._last_update = datetime.now()
        self._n_updates += 1

        log.info("online_update_complete", n_updates=self._n_updates)

    def force_update(self) -> None:
        """Force model update (ignore time/batch size constraints)."""
        self._update_model()

    def get_statistics(self) -> dict[str, float]:
        """Get learning statistics."""
        return {
            "n_updates": float(self._n_updates),
            "buffer_size": float(len(self._buffer)),
            "sparsity": float(np.sum(self.optimizer.w == 0) / self.optimizer.n_features),
            "l1_norm": float(np.sum(np.abs(self.optimizer.w))),
            "l2_norm": float(np.sqrt(np.sum(self.optimizer.w**2))),
        }


@dataclass
class FeatureWarmupConfig:
    """Configuration for gradual feature rollout.

    Industry practice (LinkedIn/Uber):
    - New features start with 0% traffic
    - Ramp up to 10% over 3 days (monitor quality)
    - Ramp to 50% over 7 days
    - Full rollout at 100% after 14 days
    """

    feature_name: str
    start_date: datetime
    ramp_schedule: list[tuple[int, float]]  # [(days, traffic_pct)]
    is_active: bool = False


class FeatureWarmupManager:
    """Gradual feature rollout to prevent quality degradation."""

    def __init__(self) -> None:
        """Initialize feature warmup manager."""
        self._configs: dict[str, FeatureWarmupConfig] = {}
        log.info("feature_warmup_manager_init")

    def add_feature(
        self,
        *,
        feature_name: str,
        ramp_schedule: list[tuple[int, float]] | None = None,
    ) -> None:
        """Add new feature with warmup schedule.

        Args:
            feature_name: Feature identifier
            ramp_schedule: [(days_since_start, traffic_pct)]
                Default: [(0, 0.0), (3, 0.1), (7, 0.5), (14, 1.0)]
        """
        if ramp_schedule is None:
            ramp_schedule = [(0, 0.0), (3, 0.1), (7, 0.5), (14, 1.0)]

        config = FeatureWarmupConfig(
            feature_name=feature_name,
            start_date=datetime.now(),
            ramp_schedule=ramp_schedule,
        )
        self._configs[feature_name] = config

        log.info("feature_warmup_added", feature_name=feature_name)

    def get_traffic_pct(self, *, feature_name: str) -> float:
        """Get current traffic percentage for feature.

        Args:
            feature_name: Feature identifier

        Returns:
            Traffic percentage (0.0-1.0)
        """
        if feature_name not in self._configs:
            return 1.0  # Unknown features get full traffic

        config = self._configs[feature_name]
        days_elapsed = (datetime.now() - config.start_date).days

        # Find current stage in ramp schedule
        traffic_pct = 0.0
        for days, pct in config.ramp_schedule:
            if days_elapsed >= days:
                traffic_pct = pct
            else:
                break

        return traffic_pct

    def should_use_feature(self, *, feature_name: str, user_id: str) -> bool:
        """Determine if feature should be used for this user (hash-based).

        Args:
            feature_name: Feature identifier
            user_id: User identifier

        Returns:
            True if feature should be used, False otherwise
        """
        traffic_pct = self.get_traffic_pct(feature_name=feature_name)

        if traffic_pct >= 1.0:
            return True
        if traffic_pct <= 0.0:
            return False

        # Hash-based sampling (stable per user)
        hash_value = hash(f"{feature_name}:{user_id}") % 10000
        threshold = int(traffic_pct * 10000)

        return hash_value < threshold
