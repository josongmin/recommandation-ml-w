variable "project_name" {
  type        = string
  description = "Project name (used in resource naming)"
  default     = "rec-ml"
}

variable "environment" {
  type        = string
  description = "Environment name (dev/staging/prod)"
  default     = "dev"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "ap-northeast-2" # Seoul
}
