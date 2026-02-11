terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — uncomment when ready
  # backend "s3" {
  #   bucket = "wine-rec-terraform-state"
  #   key    = "dev/terraform.tfstate"
  #   region = "ap-northeast-2"
  # }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "ap-northeast-2"
}

module "storage" {
  source  = "../../modules/storage"
  project = "wine-rec"
  env     = "dev"
}
