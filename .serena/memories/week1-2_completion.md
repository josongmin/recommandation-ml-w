# Week 1-2 완료 보고서 (Storage Foundation)

## 완료 날짜
2026-02-11

## 산출물 (RFC-EXEC-PLAN-014 §1 기준)

### ✅ Week 1: IaC 기초 + S3 + IAM
```
✓ infra/terraform/modules/storage/ — 완료
✓ S3 버킷: wine-rec-dev-data (versioning enabled)
✓ IAM: 5개 Role (Lambda/Glue/SageMaker/Fargate execution/Fargate task)
✓ VPC: 10.0.0.0/16 + private/public subnet (2AZ)
```

### ✅ Week 2: DynamoDB + Glue Catalog
```
✓ infra/terraform/modules/feature_store/ — 완료
✓ DynamoDB: 2개 테이블 (PAY_PER_REQUEST)
  - features_online_v1 (entity_type/entity_id)
  - user_profile_v1 (user_id)
✓ Glue Catalog: wine_rec_dev database
```

## Terraform 파일 구조
```
infra/terraform/
├── envs/dev/
│   ├── main.tf (8개 리소스)
│   └── variables.tf (project_name/environment/aws_region)
├── modules/
│   ├── storage/
│   │   ├── main.tf (S3/IAM/VPC/Glue)
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── feature_store/
│       ├── main.tf (DynamoDB 2종)
│       ├── variables.tf
│       └── outputs.tf
├── .gitignore
└── README.md
```

## 검증
- `terraform init`: ✓ 성공
- `terraform validate`: ✓ Success
- `terraform fmt`: ✓ 포맷팅 완료

## 시드 데이터 생성
```
data/
├── gold_a/ (120 wines, 210 SKUs, 600 reviews)
├── gold_b/ (IR 4종)
├── bronze/ (2000 impressions, 1368 actions, 165 orders)
└── profiles/ (200 users)
```

## 테스트 결과
- 355개 테스트 전체 통과
- Coverage: 72.8% (목표 55% 초과)

## 예상 비용 (배포 시)
- S3: ~$1/month
- DynamoDB (PAY_PER_REQUEST): ~$5/month
- VPC: Free
- **Total: ~$6/month**

## 다음 작업 (Week 3-4)
- Ingestion 모듈 (API Gateway + Kinesis + Lambda)
- Event 검증 로직 구현 (RFC-LOG-SCHEMA-009)
