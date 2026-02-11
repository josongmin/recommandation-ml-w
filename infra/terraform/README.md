# Wine Rec Terraform Infrastructure

## 구조

```
infra/terraform/
├── envs/dev/           # Dev environment
│   ├── main.tf
│   └── variables.tf
├── modules/
│   ├── storage/        # S3 + IAM + VPC + Glue
│   ├── feature_store/  # DynamoDB
│   ├── ingestion/      # API GW + Kinesis + Lambda (Week 3-4)
│   └── serving/        # Fargate + ALB (Week 13-14)
└── README.md
```

## Quick Start

```bash
cd infra/terraform/envs/dev

# Initialize
terraform init

# Plan
terraform plan

# Apply
terraform apply
```

## Modules

### storage
- S3 data lake (Bronze/Silver/Gold)
- Lifecycle policies
- IAM Roles (Lambda/Glue/SageMaker/Fargate)
- VPC + VPC Endpoints
- Glue Data Catalog

### feature_store
- DynamoDB features_online_v1
- DynamoDB user_profile_v1

## Outputs

```bash
terraform output s3_bucket_name
terraform output glue_catalog_database
terraform output dynamodb_features_table
```

## Cost Estimation (Week 1-2)

- S3 (first 50GB): ~$1/month
- DynamoDB (PAY_PER_REQUEST, low traffic): ~$5/month
- VPC/VPC Endpoints: Free
- Glue Catalog: Free (first 1M requests)
- **Total: ~$6/month**
