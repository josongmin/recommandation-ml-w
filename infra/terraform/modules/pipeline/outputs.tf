output "step_functions_arn" {
  value       = aws_sfn_state_machine.daily_pipeline.arn
  description = "Step Functions daily pipeline ARN"
}

output "glue_bronze_to_silver_job" {
  value       = aws_glue_job.bronze_to_silver.name
  description = "Glue bronze_to_silver job name"
}

output "glue_silver_to_gold_a_job" {
  value       = aws_glue_job.silver_to_gold_a.name
  description = "Glue silver_to_gold_a job name"
}

output "glue_gold_a_to_gold_b_job" {
  value       = aws_glue_job.gold_a_to_gold_b.name
  description = "Glue gold_a_to_gold_b job name"
}

output "glue_dataset_builder_job" {
  value       = aws_glue_job.dataset_builder.name
  description = "Glue dataset_builder job name"
}

output "eventbridge_rule_arn" {
  value       = aws_cloudwatch_event_rule.daily_pipeline.arn
  description = "EventBridge daily schedule rule ARN"
}
