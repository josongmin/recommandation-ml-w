# Week 3-4 진행 계획 (Ingestion Pipeline)

## 완료 항목 (2026-02-11)

### ✅ Terraform 모듈 작성
```
infra/terraform/modules/ingestion/
├── main.tf         # API GW + Kinesis + Lambda + Firehose
├── variables.tf    # lambda_zip_path, s3_bucket_arn 등
└── outputs.tf      # API endpoint, stream names
```

**생성 리소스**:
- API Gateway HTTP API (POST /events)
- Kinesis Data Stream (ON_DEMAND)
- Lambda (event validator)
- Kinesis Firehose → S3 Bronze (Parquet)
- IAM Role (Firehose)
- CloudWatch Logs (3종)

### ✅ Lambda 함수 구현
```python
src/wine_rec/ingestion/lambda_handler.py
- API Gateway v2 event 파싱
- validate_and_route() 호출
- Kinesis putRecord
- Partition key 결정 (user_id/wine_sku_id/impression_id)
- Error handling (400/500)
```

### ✅ 빌드 스크립트
```bash
scripts/build_lambda_package.sh
# → lambda_deployment.zip 생성
```

## 남은 작업

### Week 3 (검증 & 통합)
- [ ] Lambda 테스트 추가 (handler + Kinesis mock)
- [ ] Terraform ingestion 모듈을 dev/main.tf에 통합
- [ ] `terraform plan` 확인
- [ ] Glue Table 정의 (event_logs_v1 스키마)

### Week 4 (Firehose 완성)
- [ ] Firehose Parquet 변환 테스트
- [ ] S3 Bronze 경로 규약 문서화
- [ ] 통합 테스트: curl → API → Kinesis → S3
- [ ] DynamoDB feature 갱신 Lambda (Consumer)

## RFC 기준 검증

### RFC-LOG-SCHEMA-009 준수
- ✓ ImpressionEvent, ActionEvent, OrderEvent, PolicyEvent 스키마
- ✓ schema_version 필드 검증
- ✓ Pydantic ValidationError 처리

### RFC-INFRA-IMPL-013 §1-2 준수
- ✓ API Gateway HTTP API
- ✓ Kinesis On-demand
- ✓ Lambda Python 3.11
- ✓ Firehose → S3 Parquet (5MB/5min buffer)

## 예상 비용 (Week 3-4 추가)
- API Gateway: $1/million requests (~$1/month)
- Kinesis Data Stream (On-demand): ~$5/month
- Lambda: 거의 무료 (Free Tier)
- Firehose: ~$2/month
- **Total 추가: ~$8/month**
- **누적: ~$14/month**
