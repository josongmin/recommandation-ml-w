output "business_dashboard_name" {
  value       = aws_cloudwatch_dashboard.business_metrics.dashboard_name
  description = "Business metrics dashboard name"
}

output "ab_test_dashboard_name" {
  value       = aws_cloudwatch_dashboard.ab_test.dashboard_name
  description = "A/B test dashboard name"
}

output "alert_topic_arn" {
  value       = aws_sns_topic.alerts.arn
  description = "SNS topic ARN for alerts"
}

# output "metric_publisher_function_name" {
#   value       = aws_lambda_function.metric_publisher.function_name
#   description = "Metric publisher Lambda function name"
# }

output "evaluation_schedule_arn" {
  value       = aws_cloudwatch_event_rule.daily_evaluation.arn
  description = "Daily evaluation EventBridge rule ARN"
}
