# Week 11-12 완료 보고서 (Model Training)

## 완료 날짜
2026-02-11

## 산출물 (RFC-EXEC-PLAN-014 §11-12 기준)

### ✅ 4종 Baseline Models (Pure PyTorch)
```python
1. BPR (Bayesian Personalized Ranking)
   - Matrix Factorization + pairwise ranking loss
   - Papers: Rendle et al., UAI 2009
   - Complexity: O(B × D) (매우 빠름)
   - 25 tests passed

2. Two-Tower (DSSM)
   - Dual-encoder: User tower + Item tower
   - L2-normalized embeddings (ANN-friendly)
   - Papers: Huang et al., CIKM 2013

3. LightGCN (Graph Neural Network)
   - User-Item bipartite graph
   - K-layer neighbor aggregation
   - Papers: He et al., SIGIR 2020 (SOTA GNN for CF)

4. DeepFM (Feature Interaction)
   - FM (2nd order) + Deep (high-order)
   - Papers: Guo et al., IJCAI 2017
```

### ✅ Hyperparameter Tuning (Optuna)
```python
src/wine_rec/models/training/optuna_tuner.py
- Bayesian optimization for HPO
- Objectives: objective_bpr, objective_lightgcn, objective_two_tower
- Search space:
  * embedding_dim: [32, 64, 128, 256]
  * learning_rate: [1e-5, 1e-2] (log scale)
  * weight_decay: [1e-7, 1e-3] (log scale)
  * n_layers: [2, 5] (LightGCN)
  * temperature: [0.05, 0.2] (Two-Tower)
- Visualization: optimization_history, param_importances
```

**SOTA 확장**:
- Pruning: Early stopping for unpromising trials
- Multi-objective: Maximize NDCG@10, Minimize latency
- Distributed: Optuna + Ray Tune for parallel trials

### ✅ Model Registry (S3 + DynamoDB)
```python
src/wine_rec/contracts/model_registry.py
- Protocol: save_model, load_model, list_models
- Metadata tracking:
  * model_id, version, dataset_version, feature_set_version
  * hyperparameters, metrics (val_ndcg@10, test_recall@10)
  * trained_at, s3_checkpoint_path
- Production promotion: promote_to_production, get_production_model
```

**DynamoDB Schema**:
```
Table: model_metadata
- PK: model_id (bpr_v1, lightgcn_v2)
- SK: version (v1.0.0, v1.1.0)
- GSI1: model_type_index (bpr/lightgcn/two_tower)
- GSI2: production_index (is_production=true)
```

### ✅ Terraform Training Module
```
infra/terraform/modules/training/
├── main.tf        # SageMaker + ECR + Step Functions + Lambda
├── variables.tf
└── outputs.tf
```

**생성 리소스**:
- S3 model registry bucket (versioning enabled)
- DynamoDB model_metadata table (2 GSIs)
- ECR repositories: training-bpr, training-lightgcn, training-two-tower
- SageMaker Notebook instance (ml.t3.medium)
- Lambda: model_registry (register/promote models)
- Step Functions: training_pipeline (Dataset → Train → Register)
- EventBridge: Weekly training schedule (Sunday 02:00 UTC)

### ✅ SOTA 확장 전략 ([model_training_sota.md](.serena/memories/model_training_sota.md:1))

**학계 SOTA 모델 로드맵**:
```
Phase 1 (Week 11-12): Baseline 강화
- BPR → VBPR (Visual features)
- Two-Tower → Cross-Batch Negatives
- LightGCN → Temporal LightGCN
- DeepFM → xDeepFM (CIN)

Phase 2 (Phase H): Advanced Architectures
- GRU4Rec (Session-based, ICLR 2016)
- SASRec (Self-Attention, ICDM 2018)
- BERT4Rec (WWW 2019)
- SimpleX (SIGIR 2023, SOTA on CTR)

Phase 3 (Production): Specialized
- Two-Tower + Hard Negative Mining
- Multi-task Learning (MMoE)
- Counterfactual Learning (IPS/SNIPS)
```

**업계 SOTA 프랙티스**:
```
1. Two-Stage Retrieval + Ranking (Meta/Google)
2. Exploration vs Exploitation (Spotify/Netflix)
3. Online Learning (LinkedIn/Twitter)
4. Model Distillation (TikTok/Kuaishou)
5. A/B Testing Framework
```

## Training Pipeline Workflow (Step Functions)

```json
BuildDataset (Glue)
  → TrainModels (Parallel)
      ├─ TrainBPR (SageMaker ml.p3.2xlarge)
      └─ TrainLightGCN (SageMaker ml.p3.2xlarge)
  → RegisterModels (Lambda)
  → Success
```

- **실행 주기**: Weekly (Sunday 02:00 UTC)
- **Parallel Training**: BPR + LightGCN 동시 학습
- **Instance**: ml.p3.2xlarge (V100 GPU, 1h timeout)
- **Output**: S3 models/ (checkpoint + metadata)

## 테스트 결과
- **25개 model baseline 테스트** 전체 통과
- **Coverage**: BPR 35%, Two-Tower 40%, LightGCN 40%, DeepFM 40%
- **Training functions**: train_bpr, train_lightgcn, train_two_tower, train_deepfm

## RFC 준수
- ✓ RFC-MODEL-REGISTRY-013: Model versioning + metadata tracking
- ✓ Pure PyTorch baseline (RecBole 통합 가능)
- ✓ Hyperparameter tuning (Optuna Bayesian optimization)
- ✓ Model lineage (dataset_version → model_version)

## 확장성 포인트

### 1. RecBole 통합 (선택적)
```python
# Pure PyTorch (현재)
model = BPRModel(n_users, n_items, embedding_dim=64)

# RecBole (대체 가능)
from recbole.model.general_recommender import BPR as RecBoleBPR
model = RecBoleBPR(config, dataset)

# Adapter pattern으로 interface 동일하게 유지
```

### 2. Distributed Training (PyTorch DDP)
```python
# Single GPU (현재)
model = model.to(device)

# Multi-GPU (확장)
model = DistributedDataParallel(model)
```

### 3. Model Serving Optimization
```python
# Quantization (INT8)
model_int8 = torch.quantization.quantize_dynamic(
    model, {nn.Linear}, dtype=torch.qint8
)

# ONNX Export (TorchScript)
torch.onnx.export(model, dummy_input, "model.onnx")
```

### 4. A/B Testing Framework
```python
models = {
    "baseline_bpr_v1": load_model("s3://models/bpr_v1.pth"),
    "lightgcn_v2": load_model("s3://models/lightgcn_v2.pth"),
}

def get_model_for_user(user_id):
    experiment = ab_test_config.get_experiment(user_id)
    return models[experiment]
```

## 예상 비용 (Week 11-12 추가)
- SageMaker Training (ml.p3.2xlarge, weekly 2h): ~$50/month
- SageMaker Notebook (ml.t3.medium): ~$30/month
- ECR storage (3 repos): ~$1/month
- Lambda (model registry): ~$1/month
- DynamoDB (model metadata): ~$5/month
- **Total 추가: ~$87/month**
- **누적: ~$157/month**

## 다음 작업 (Week 13-14)
- FastAPI Serving (recommender.py, explainer.py)
- Fargate Deployment (ECS cluster + ALB)
- ANN Index (FAISS/ScaNN for Two-Tower)
- Monitoring (CloudWatch + X-Ray)
