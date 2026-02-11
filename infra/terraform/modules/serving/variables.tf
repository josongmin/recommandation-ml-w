variable "project_name" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment (dev/staging/prod)"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID (from storage module)"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnet IDs for ALB (from storage module)"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for ECS tasks (from storage module)"
}

variable "fargate_execution_role_arn" {
  type        = string
  description = "IAM role ARN for Fargate execution (from storage module)"
}

variable "fargate_task_role_arn" {
  type        = string
  description = "IAM role ARN for Fargate task (from storage module)"
}

variable "model_bucket_name" {
  type        = string
  description = "S3 model registry bucket name (from training module)"
}

variable "feature_store_table" {
  type        = string
  description = "DynamoDB feature store table name (from feature_store module)"
}

variable "model_metadata_table" {
  type        = string
  description = "DynamoDB model metadata table name (from training module)"
}

variable "task_cpu" {
  type        = number
  description = "Fargate task CPU units (256, 512, 1024, 2048, 4096)"
  default     = 1024
}

variable "task_memory" {
  type        = number
  description = "Fargate task memory in MiB (512, 1024, 2048, 4096, 8192)"
  default     = 2048
}

variable "min_capacity" {
  type        = number
  description = "Minimum number of tasks"
  default     = 2
}

variable "max_capacity" {
  type        = number
  description = "Maximum number of tasks"
  default     = 10
}
