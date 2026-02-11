output "alb_dns_name" {
  value       = aws_lb.serving.dns_name
  description = "ALB DNS name for serving API"
}

output "ecr_serving_repo" {
  value       = aws_ecr_repository.serving.repository_url
  description = "ECR serving image repository"
}

output "ecs_cluster_name" {
  value       = aws_ecs_cluster.serving.name
  description = "ECS cluster name"
}

output "ecs_service_name" {
  value       = aws_ecs_service.serving.name
  description = "ECS service name"
}

output "cloudwatch_log_group" {
  value       = aws_cloudwatch_log_group.serving.name
  description = "CloudWatch log group for serving"
}

output "dashboard_name" {
  value       = aws_cloudwatch_dashboard.serving.dashboard_name
  description = "CloudWatch dashboard name"
}
