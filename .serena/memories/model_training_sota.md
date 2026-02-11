# Model Training SOTA 전략 (Week 11-12)

## 현재 구현 (Pure PyTorch Baselines)

### 1. BPR (Bayesian Personalized Ranking)
```python
# Rendle et al., UAI 2009
class BPRModel(nn.Module):
    - Matrix Factorization with pairwise ranking loss
    - Loss: -log(sigmoid(pos_score - neg_score))
    - Complexity: O(B × D) (매우 빠름)
    - Use Case: 초기 베이스라인, Cold-start user
```

**SOTA 확장**:
```python
# BPR with Side Information (VBPR, DVBPR)
class VisualBPR(BPRModel):
    def __init__(self, visual_features: torch.Tensor):
        # Wine visual features (병 이미지, 라벨 색상 등)
        self.visual_projection = nn.Linear(visual_dim, embedding_dim)

    def forward(self, user, pos, neg):
        # u · (item_emb + visual_emb)
        p_emb = self.item_embedding(pos) + self.visual_projection(self.visual_features[pos])
        ...
```

### 2. Two-Tower (DSSM)
```python
# Huang et al., CIKM 2013
class TwoTowerModel(nn.Module):
    - User tower + Item tower → cosine similarity
    - L2-normalized embeddings (ANN-friendly)
    - Use Case: Candidate retrieval (Top-K)
```

**SOTA 확장**:
```python
# Cross-Batch Negative Sampling (Google DLRM 2019)
def in_batch_negatives(user_emb: Tensor, item_emb: Tensor, temperature: float = 0.07):
    # All items in batch become negatives for all users
    scores = user_emb @ item_emb.T / temperature  # [B, B]
    labels = torch.arange(B)  # Diagonal = positive pairs
    return F.cross_entropy(scores, labels)

# Multi-task Two-Tower (MMOE, Google RecSys 2018)
class MultiTaskTwoTower(nn.Module):
    def __init__(self):
        self.shared_user_tower = _Tower(...)
        self.engagement_head = nn.Linear(D, 1)  # Task 1: Click
        self.conversion_head = nn.Linear(D, 1)  # Task 2: Purchase

    def forward(self, user_ids, item_ids):
        u = self.shared_user_tower(user_ids)
        i = self.item_tower(item_ids)
        engagement_score = self.engagement_head(u * i)
        conversion_score = self.conversion_head(u * i)
        return engagement_score, conversion_score
```

### 3. LightGCN (Graph Neural Network)
```python
# He et al., SIGIR 2020 (SOTA GNN for CF)
class LightGCNModel(nn.Module):
    - User-Item bipartite graph
    - K-layer neighbor aggregation
    - Final embedding = mean of all layers
    - Use Case: Collaborative filtering with graph structure
```

**SOTA 확장**:
```python
# LightGCN + Temporal Dynamics (TGCN, KDD 2021)
class TemporalLightGCN(LightGCNModel):
    def __init__(self, n_timestamps: int):
        self.time_embedding = nn.Embedding(n_timestamps, embedding_dim)

    def aggregate(self, layer_embeddings, timestamps):
        # Time-aware aggregation
        time_weights = torch.softmax(self.time_embedding(timestamps), dim=0)
        return (layer_embeddings * time_weights.unsqueeze(-1)).sum(dim=0)

# LightGCN + Knowledge Graph (KGAT, KDD 2019)
class KnowledgeGraphLightGCN(LightGCNModel):
    def __init__(self, kg_triples: list):
        # Wine KG: (wine_id, variety, Pinot Noir), (wine_id, region, Burgundy)
        self.kg_embeddings = nn.Embedding(n_entities, embedding_dim)
        self.relation_embeddings = nn.Embedding(n_relations, embedding_dim)

    def kg_attention(self, entity_emb, relation_emb):
        # Attention-based KG aggregation
        ...
```

### 4. DeepFM (Feature Interaction)
```python
# Guo et al., IJCAI 2017
class DeepFMModel(nn.Module):
    - FM (2nd order) + Deep (high-order) feature interactions
    - Use Case: CTR prediction with rich features
```

**SOTA 확장**:
```python
# xDeepFM (CIN, KDD 2018)
class xDeepFM(nn.Module):
    def __init__(self):
        self.cin_layers = [CINLayer(layer_size) for layer_size in [128, 64]]
        # Compressed Interaction Network: explicit feature crossing

# AutoInt (Self-Attention, CIKM 2019)
class AutoInt(nn.Module):
    def __init__(self):
        self.attention = nn.MultiheadAttention(embed_dim, num_heads)
        # Self-attention on feature embeddings → automatic feature interaction

# FiBiNET (Bilinear Interaction, RecSys 2019)
class FiBiNET(nn.Module):
    def bilinear_interaction(self, field_i, field_j):
        # W_ij parametrizes interaction between field i and j
        return field_i @ self.W[i, j] @ field_j.T
```

## 학계 SOTA 모델 로드맵

### Phase 1 (Week 11-12): Baseline 강화
```python
1. BPR → VBPR (Visual features)
2. Two-Tower → Cross-Batch Negatives
3. LightGCN → Temporal LightGCN
4. DeepFM → xDeepFM (CIN)
```

### Phase 2 (Phase H): Advanced Architectures
```python
5. GRU4Rec (Session-based, ICLR 2016)
   - Sequential recommendation
   - RNN for session modeling

6. SASRec (Self-Attention, ICDM 2018)
   - Transformer for sequential rec
   - Positional encoding for order

7. BERT4Rec (WWW 2019)
   - Bidirectional Transformer
   - Masked item prediction (MLM)

8. SimpleX (SIGIR 2023, SOTA on CTR)
   - Simplicity wins: MLP + cosine similarity
   - State-of-the-art on Criteo/Avazu
```

### Phase 3 (Production): Specialized Models
```python
9. Two-Tower with Hard Negative Mining
   - Online hard negative mining from serving logs
   - Temperature-scaled softmax

10. Multi-task Learning (MMoE, Google 2018)
    - Shared bottom + Expert gating
    - Tasks: Click, Add-to-cart, Purchase, Dwell

11. Counterfactual Learning (IPS/SNIPS)
    - Debiasing with propensity scores
    - Policy learning from historical data
```

## 업계 SOTA 프로덕션 패턴

### 1. Two-Stage Retrieval + Ranking (Meta/Google)
```python
# Stage 1: Candidate Retrieval (Two-Tower ANN)
candidates = two_tower_model.retrieve_top_k(user_emb, k=500)

# Stage 2: Ranking (DeepFM with rich features)
ranked = deepfm_model.rank(user_features, candidate_features)
return ranked[:10]
```

### 2. Exploration vs Exploitation (Spotify/Netflix)
```python
# Epsilon-greedy
if random() < epsilon:
    return random_sample(candidates, k=3)  # Exploration
else:
    return model_top_k(candidates, k=10)   # Exploitation

# Thompson Sampling (Bayesian)
for item in candidates:
    theta = sample_from_posterior(item)
    scores[item] = theta
return top_k(scores)
```

### 3. Online Learning (LinkedIn/Twitter)
```python
# Incremental updates (not full retraining)
class OnlineTwoTower:
    def partial_fit(self, user_id, positive_item, negative_items):
        # SGD update on new interaction
        loss = contrastive_loss(user_id, positive_item, negative_items)
        optimizer.step()

    def get_user_embedding(self, user_id):
        # Real-time user embedding
        return self.user_tower(user_id)
```

### 4. Model Distillation (TikTok/Kuaishou)
```python
# Teacher: Large LightGCN (10-layer)
teacher = LightGCNModel(n_layers=10, embedding_dim=256)

# Student: Small Two-Tower (fast serving)
student = TwoTowerModel(embedding_dim=64)

# Distillation loss
def distill_loss(student_scores, teacher_scores, temperature=3.0):
    soft_targets = F.softmax(teacher_scores / temperature, dim=1)
    soft_student = F.log_softmax(student_scores / temperature, dim=1)
    return F.kl_div(soft_student, soft_targets)
```

### 5. A/B Testing Framework
```python
# Model Registry
models = {
    "baseline_bpr_v1": BPRModel.load("s3://models/bpr_v1.pth"),
    "lightgcn_v2": LightGCNModel.load("s3://models/lightgcn_v2.pth"),
    "two_tower_v3": TwoTowerModel.load("s3://models/two_tower_v3.pth"),
}

# Traffic splitting
def get_model_for_user(user_id):
    experiment = ab_test_config.get_experiment(user_id)
    if experiment == "control":
        return models["baseline_bpr_v1"]
    elif experiment == "treatment_a":
        return models["lightgcn_v2"]
    else:
        return models["two_tower_v3"]
```

## Hyperparameter Tuning (Optuna)

```python
def objective(trial):
    # Suggest hyperparameters
    lr = trial.suggest_float("lr", 1e-5, 1e-2, log=True)
    embedding_dim = trial.suggest_categorical("embedding_dim", [64, 128, 256])
    weight_decay = trial.suggest_float("weight_decay", 1e-6, 1e-3, log=True)
    n_layers = trial.suggest_int("n_layers", 2, 5)

    # Train model
    model = LightGCNModel(n_layers=n_layers, embedding_dim=embedding_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    val_ndcg = train_and_evaluate(model, optimizer, epochs=10)

    return val_ndcg  # Maximize

# Run tuning
study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=50)

print(f"Best params: {study.best_params}")
print(f"Best NDCG@10: {study.best_value}")
```

## Model Registry + Versioning

```python
# Save model with metadata
def save_model(model, metadata: dict, output_path: str):
    torch.save({
        "model_state_dict": model.state_dict(),
        "metadata": {
            "model_type": "LightGCN",
            "version": "v2.1",
            "dataset_version": "ds_v3",
            "feature_set_version": "fs_v2",
            "hyperparameters": {
                "n_layers": 3,
                "embedding_dim": 128,
                "lr": 0.001,
            },
            "metrics": {
                "val_recall@10": 0.352,
                "val_ndcg@10": 0.428,
                "test_recall@10": 0.348,
            },
            "trained_at": datetime.now().isoformat(),
        }
    }, output_path)

# Load model with versioning
def load_model(model_path: str) -> tuple[nn.Module, dict]:
    checkpoint = torch.load(model_path)
    metadata = checkpoint["metadata"]

    # Instantiate model from metadata
    if metadata["model_type"] == "LightGCN":
        model = LightGCNModel(**metadata["hyperparameters"])
        model.load_state_dict(checkpoint["model_state_dict"])

    return model, metadata
```

## 확장성 보장

### 1. Pluggable Model Architecture
```python
# Abstract base class
class RecommenderModel(nn.Module):
    @abstractmethod
    def predict_top_k(self, user_id: int, k: int) -> list[int]:
        pass

    @abstractmethod
    def save_checkpoint(self, path: str) -> None:
        pass

# Easy to add new models
class NewSOTAModel(RecommenderModel):
    def predict_top_k(self, user_id, k):
        ...
```

### 2. RecBole 통합 (선택적)
```python
# Pure PyTorch (현재)
model = BPRModel(n_users, n_items, embedding_dim=64)

# RecBole (대체 가능)
from recbole.model.general_recommender import BPR as RecBoleBPR
model = RecBoleBPR(config, dataset)

# Interface 동일하게 유지 (Adapter pattern)
class RecBoleAdapter(RecommenderModel):
    def __init__(self, recbole_model):
        self.model = recbole_model

    def predict_top_k(self, user_id, k):
        return self.model.full_sort_predict(user_id)[:k]
```

### 3. Distributed Training (PyTorch DDP)
```python
# Single GPU (현재)
model = LightGCNModel(...)
model = model.to(device)

# Multi-GPU (확장)
model = LightGCNModel(...)
model = nn.DataParallel(model)  # Simple parallel
# OR
model = DistributedDataParallel(model)  # DDP (faster)
```

## 결론

✓ **4종 Baseline 완성**: BPR, Two-Tower, LightGCN, DeepFM (Pure PyTorch)
✓ **SOTA 확장 패스**: Visual features, Cross-batch negatives, Temporal GCN, xDeepFM
✓ **업계 패턴**: Two-stage, Exploration, Online learning, Distillation, A/B testing
✓ **Hyperparameter Tuning**: Optuna 통합 준비
✓ **Model Registry**: 버전 관리 + 메타데이터 추적
✓ **확장성**: Pluggable architecture, RecBole 통합 가능, Distributed training 지원

**학계/업계 SOTA 보장**: 최신 논문 재현 + 프로덕션 프랙티스
