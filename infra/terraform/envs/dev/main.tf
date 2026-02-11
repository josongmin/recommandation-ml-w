terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

variable "aws_region" {
  default = "ap-northeast-2"
}

module "storage" {
  source = "../../modules/storage"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
}

module "feature_store" {
  source = "../../modules/feature_store"

  project_name = var.project_name
  environment  = var.environment
}

module "ingestion" {
  source = "../../modules/ingestion"

  project_name          = var.project_name
  environment           = var.environment
  lambda_role_arn       = module.storage.iam_lambda_role_arn
  s3_bucket_arn         = module.storage.s3_bucket_arn
  glue_catalog_database = module.storage.glue_catalog_database
  lambda_zip_path       = "${path.root}/../../../../lambda_deployment.zip"
}

module "pipeline" {
  source = "../../modules/pipeline"

  project_name   = var.project_name
  environment    = var.environment
  glue_role_arn  = module.storage.iam_glue_role_arn
  s3_bucket_name = module.storage.s3_bucket_name
}

module "kinesis" {
  source       = "../../modules/kinesis"
  project      = "wine-rec"
  env          = "dev"
  stream_name  = "wine-events-stream"
}
