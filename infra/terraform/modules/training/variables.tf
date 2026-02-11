variable "project_name" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment (dev/staging/prod)"
}

variable "sagemaker_role_arn" {
  type        = string
  description = "IAM role ARN for SageMaker (from storage module)"
}

variable "lambda_role_arn" {
  type        = string
  description = "IAM role ARN for Lambda (from storage module)"
}

variable "step_functions_role_arn" {
  type        = string
  description = "IAM role ARN for Step Functions (from pipeline module)"
}

variable "eventbridge_role_arn" {
  type        = string
  description = "IAM role ARN for EventBridge (from pipeline module)"
}

variable "dataset_builder_job_name" {
  type        = string
  description = "Glue dataset builder job name (from pipeline module)"
}

variable "lambda_deployment_package" {
  type        = string
  description = "Path to Lambda deployment zip (build with: just build-lambda-training)"
  default     = "lambda_deployment.zip"
}
