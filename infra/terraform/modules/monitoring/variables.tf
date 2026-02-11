variable "project_name" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment (dev/staging/prod)"
}

variable "serving_log_group" {
  type        = string
  description = "CloudWatch log group for serving (from serving module)"
}

variable "lambda_role_arn" {
  type        = string
  description = "IAM role ARN for Lambda (from storage module)"
}

variable "eventbridge_role_arn" {
  type        = string
  description = "IAM role ARN for EventBridge (from pipeline module)"
}

variable "evaluation_job_name" {
  type        = string
  description = "Glue evaluation job name"
  default     = "evaluation_job"
}

variable "alert_email" {
  type        = string
  description = "Email address for alert notifications"
  default     = ""
}

variable "ctr_threshold" {
  type        = number
  description = "CTR alarm threshold (e.g., 0.03 = 3%)"
  default     = 0.03
}

variable "conversion_rate_threshold" {
  type        = number
  description = "Conversion rate alarm threshold (e.g., 0.01 = 1%)"
  default     = 0.01
}

variable "ndcg_threshold" {
  type        = number
  description = "NDCG@10 alarm threshold (e.g., 0.35)"
  default     = 0.35
}
