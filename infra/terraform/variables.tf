variable "project" {
  description = "Project name prefix"
  type        = string
  default     = "wine-rec"
}

variable "env" {
  description = "Environment (dev/prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-2"
}
