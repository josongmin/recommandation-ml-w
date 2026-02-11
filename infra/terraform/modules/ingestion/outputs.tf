output "api_endpoint" {
  value       = aws_apigatewayv2_api.http.api_endpoint
  description = "API Gateway endpoint URL"
}

output "kinesis_stream_name" {
  value       = aws_kinesis_stream.events.name
  description = "Kinesis data stream name"
}

output "kinesis_stream_arn" {
  value       = aws_kinesis_stream.events.arn
  description = "Kinesis data stream ARN"
}

output "firehose_delivery_stream_name" {
  value       = aws_kinesis_firehose_delivery_stream.bronze.name
  description = "Firehose delivery stream name"
}

output "lambda_function_name" {
  value       = aws_lambda_function.validator.function_name
  description = "Event validator Lambda function name"
}
