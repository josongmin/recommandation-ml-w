output "s3_bucket_name" {
  value       = aws_s3_bucket.data.id
  description = "S3 data lake bucket name"
}

output "s3_bucket_arn" {
  value       = aws_s3_bucket.data.arn
  description = "S3 data lake bucket ARN"
}

output "glue_catalog_database" {
  value       = aws_glue_catalog_database.main.name
  description = "Glue catalog database name"
}

output "iam_lambda_role_arn" {
  value       = aws_iam_role.lambda.arn
  description = "IAM role ARN for Lambda"
}

output "iam_glue_role_arn" {
  value       = aws_iam_role.glue.arn
  description = "IAM role ARN for Glue"
}

output "iam_sagemaker_role_arn" {
  value       = aws_iam_role.sagemaker.arn
  description = "IAM role ARN for SageMaker"
}

output "iam_fargate_role_arn" {
  value       = aws_iam_role.fargate_task.arn
  description = "IAM role ARN for Fargate tasks"
}

output "iam_fargate_execution_role_arn" {
  value       = aws_iam_role.fargate_execution.arn
  description = "IAM role ARN for Fargate execution"
}

output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}

output "private_subnet_ids" {
  value       = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  description = "Private subnet IDs"
}

output "public_subnet_ids" {
  value       = [aws_subnet.public_a.id, aws_subnet.public_b.id]
  description = "Public subnet IDs"
}
