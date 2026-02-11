# Feature Store Module - DynamoDB tables

resource "aws_dynamodb_table" "features_online" {
  name         = "${var.project_name}-${var.environment}-features-online-v1"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "entity_type"
  range_key    = "entity_id"

  attribute {
    name = "entity_type"
    type = "S"
  }

  attribute {
    name = "entity_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "user_profile" {
  name         = "${var.project_name}-${var.environment}-user-profile-v1"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
}
