output "model_bucket_name" {
  value       = aws_s3_bucket.models.id
  description = "S3 model registry bucket name"
}

output "model_metadata_table" {
  value       = aws_dynamodb_table.model_metadata.name
  description = "DynamoDB model metadata table name"
}

output "training_pipeline_arn" {
  value       = aws_sfn_state_machine.training_pipeline.arn
  description = "Step Functions training pipeline ARN"
}

output "ecr_bpr_repo" {
  value       = aws_ecr_repository.training_bpr.repository_url
  description = "ECR BPR training image repository"
}

output "ecr_lightgcn_repo" {
  value       = aws_ecr_repository.training_lightgcn.repository_url
  description = "ECR LightGCN training image repository"
}

output "ecr_two_tower_repo" {
  value       = aws_ecr_repository.training_two_tower.repository_url
  description = "ECR Two-Tower training image repository"
}
