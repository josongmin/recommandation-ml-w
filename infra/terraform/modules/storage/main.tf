# S3 Data Lake + Lifecycle (RFC-INFRA-IMPL-013 §1-1)

variable "project" {
  type = string
}

variable "env" {
  type = string
}

resource "aws_s3_bucket" "data" {
  bucket = "${var.project}-${var.env}-data"
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "gold-tiering"
    status = "Enabled"
    filter {
      prefix = "gold/"
    }
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 365
      storage_class = "GLACIER_INSTANT_RETRIEVAL"
    }
  }

  rule {
    id     = "logs-tiering"
    status = "Enabled"
    filter {
      prefix = "logs/"
    }
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 180
      storage_class = "GLACIER_INSTANT_RETRIEVAL"
    }
  }

  rule {
    id     = "artifacts-archive"
    status = "Enabled"
    filter {
      prefix = "artifacts/"
    }
    transition {
      days          = 365
      storage_class = "GLACIER_INSTANT_RETRIEVAL"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "bucket_name" {
  value = aws_s3_bucket.data.id
}

output "bucket_arn" {
  value = aws_s3_bucket.data.arn
}
