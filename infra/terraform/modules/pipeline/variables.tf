variable "project_name" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment (dev/staging/prod)"
}

variable "s3_bucket_name" {
  type        = string
  description = "S3 data lake bucket name (from storage module)"
}

variable "glue_role_arn" {
  type        = string
  description = "IAM role ARN for Glue jobs (from storage module)"
}
