variable "project_name" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment (dev/staging/prod)"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
}

# ── S3 Lifecycle ──
variable "bronze_transition_days" {
  type        = number
  description = "Days before transitioning Bronze to IA"
  default     = 90
}

variable "bronze_expiration_days" {
  type        = number
  description = "Days before expiring Bronze data"
  default     = 365
}

variable "silver_transition_days" {
  type        = number
  description = "Days before transitioning Silver to IA"
  default     = 180
}

variable "silver_expiration_days" {
  type        = number
  description = "Days before expiring Silver data"
  default     = 730
}

variable "gold_transition_days" {
  type        = number
  description = "Days before transitioning Gold to IA"
  default     = 365
}

variable "gold_expiration_days" {
  type        = number
  description = "Days before expiring Gold data (null = never)"
  default     = null
}
