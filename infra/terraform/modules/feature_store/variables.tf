variable "project_name" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment (dev/staging/prod)"
}

variable "features_online_read_capacity" {
  type        = number
  description = "Read capacity units (only for PROVISIONED billing)"
  default     = 5
}

variable "features_online_write_capacity" {
  type        = number
  description = "Write capacity units (only for PROVISIONED billing)"
  default     = 5
}

variable "user_profile_read_capacity" {
  type        = number
  description = "Read capacity units (only for PROVISIONED billing)"
  default     = 5
}

variable "user_profile_write_capacity" {
  type        = number
  description = "Write capacity units (only for PROVISIONED billing)"
  default     = 5
}
