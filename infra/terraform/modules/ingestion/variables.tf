variable "project_name" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment (dev/staging/prod)"
}

variable "lambda_role_arn" {
  type        = string
  description = "IAM role ARN for Lambda (from storage module)"
}

variable "s3_bucket_arn" {
  type        = string
  description = "S3 data lake bucket ARN (from storage module)"
}

variable "glue_catalog_database" {
  type        = string
  description = "Glue catalog database name (from storage module)"
}

variable "lambda_zip_path" {
  type        = string
  description = "Path to Lambda deployment package (.zip)"
  default     = "lambda_deployment.zip"
}
