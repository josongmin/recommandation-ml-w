output "features_online_table_name" {
  value       = aws_dynamodb_table.features_online.name
  description = "DynamoDB features_online_v1 table name"
}

output "features_online_table_arn" {
  value       = aws_dynamodb_table.features_online.arn
  description = "DynamoDB features_online_v1 table ARN"
}

output "user_profile_table_name" {
  value       = aws_dynamodb_table.user_profile.name
  description = "DynamoDB user_profile_v1 table name"
}

output "user_profile_table_arn" {
  value       = aws_dynamodb_table.user_profile.arn
  description = "DynamoDB user_profile_v1 table ARN"
}
