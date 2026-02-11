# DynamoDB Feature Store (RFC-INFRA-IMPL-013 §1-4)

variable "project" {
  type = string
}

variable "env" {
  type = string
}

resource "aws_dynamodb_table" "features_online" {
  name         = "${var.project}-${var.env}-features-online-v1"
  billing_mode = "PAY_PER_REQUEST" # On-demand

  hash_key  = "pk"
  range_key = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "user_profile" {
  name         = "${var.project}-${var.env}-user-profile-v1"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "pk"
  range_key = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }
}
