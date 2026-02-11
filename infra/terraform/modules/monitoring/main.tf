# ══════════════════════════════════════════════════════════════════════════════
# Monitoring Module (Week 15-16)
# - CloudWatch Dashboards (Business metrics + System metrics)
# - CloudWatch Alarms (Anomaly detection)
# - EventBridge Rules (Scheduled evaluation jobs)
# - SNS Topics (Alert notifications)
# ══════════════════════════════════════════════════════════════════════════════

# ── CloudWatch: Business Metrics Dashboard ──
resource "aws_cloudwatch_dashboard" "business_metrics" {
  dashboard_name = "${var.project_name}-${var.environment}-business-metrics"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["${var.project_name}", "ctr", { stat = "Average", label = "CTR" }],
            [".", "conversion_rate", { stat = "Average", label = "Conversion Rate" }],
            [".", "aov", { stat = "Average", label = "AOV ($)" }]
          ]
          period = 300
          region = data.aws_region.current.name
          title  = "Engagement & Revenue Metrics"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["${var.project_name}", "ndcg@10", { stat = "Average", label = "NDCG@10" }],
            [".", "recall@10", { stat = "Average", label = "Recall@10" }],
            [".", "diversity_score", { stat = "Average", label = "Diversity" }]
          ]
          period = 300
          region = data.aws_region.current.name
          title  = "Recommendation Quality Metrics"
          yAxis = {
            left = {
              min = 0
              max = 1
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", { stat = "Average", label = "p50 Latency" }],
            ["...", { stat = "p95", label = "p95 Latency" }],
            ["...", { stat = "p99", label = "p99 Latency" }]
          ]
          period = 300
          region = data.aws_region.current.name
          title  = "Serving Latency (ms)"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type = "log"
        properties = {
          query  = <<-EOQ
            SOURCE '${var.serving_log_group}'
            | fields @timestamp, ctr, conversion_rate
            | stats avg(ctr) as avg_ctr, avg(conversion_rate) as avg_cvr by bin(5m)
          EOQ
          region = data.aws_region.current.name
          title  = "Real-time CTR & CVR (5min bins)"
        }
      }
    ]
  })
}

# ── CloudWatch: A/B Test Dashboard ──
resource "aws_cloudwatch_dashboard" "ab_test" {
  dashboard_name = "${var.project_name}-${var.environment}-ab-test"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["${var.project_name}/ab_test", "variant_baseline_ctr", { stat = "Average", label = "Baseline CTR" }],
            [".", "variant_challenger_ctr", { stat = "Average", label = "Challenger CTR" }]
          ]
          period = 300
          region = data.aws_region.current.name
          title  = "A/B Test: CTR Comparison"
          annotations = {
            horizontal = [
              {
                label = "Baseline"
                value = 0.05
              }
            ]
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["${var.project_name}/ab_test", "variant_baseline_revenue", { stat = "Sum", label = "Baseline Revenue" }],
            [".", "variant_challenger_revenue", { stat = "Sum", label = "Challenger Revenue" }]
          ]
          period = 3600
          region = data.aws_region.current.name
          title  = "A/B Test: Revenue Comparison (hourly)"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["${var.project_name}/ab_test", "p_value", { stat = "Minimum", label = "p-value" }]
          ]
          period = 300
          region = data.aws_region.current.name
          title  = "Statistical Significance (p-value)"
          annotations = {
            horizontal = [
              {
                label = "Significance threshold (0.05)"
                value = 0.05
                fill  = "below"
              }
            ]
          }
        }
      }
    ]
  })
}

# ── SNS: Alert Topic ──
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.environment}-alerts"

  tags = {
    Name = "${var.project_name}-${var.environment}-alerts"
  }
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── CloudWatch Alarms: Business Metrics ──
resource "aws_cloudwatch_metric_alarm" "low_ctr" {
  alarm_name          = "${var.project_name}-${var.environment}-low-ctr"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ctr"
  namespace           = var.project_name
  period              = 300
  statistic           = "Average"
  threshold           = var.ctr_threshold
  alarm_description   = "CTR dropped below threshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-low-ctr"
  }
}

resource "aws_cloudwatch_metric_alarm" "low_conversion_rate" {
  alarm_name          = "${var.project_name}-${var.environment}-low-conversion"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "conversion_rate"
  namespace           = var.project_name
  period              = 300
  statistic           = "Average"
  threshold           = var.conversion_rate_threshold
  alarm_description   = "Conversion rate dropped below threshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-low-conversion"
  }
}

resource "aws_cloudwatch_metric_alarm" "low_ndcg" {
  alarm_name          = "${var.project_name}-${var.environment}-low-ndcg"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ndcg@10"
  namespace           = var.project_name
  period              = 3600
  statistic           = "Average"
  threshold           = var.ndcg_threshold
  alarm_description   = "NDCG@10 quality degradation"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-low-ndcg"
  }
}

# ── CloudWatch Alarms: Anomaly Detection ──
resource "aws_cloudwatch_metric_alarm" "ctr_anomaly" {
  alarm_name                = "${var.project_name}-${var.environment}-ctr-anomaly"
  comparison_operator       = "LessThanLowerOrGreaterThanUpperThreshold"
  evaluation_periods        = 2
  threshold_metric_id       = "e1"
  alarm_description         = "CTR anomaly detected (ML-based)"
  alarm_actions             = [aws_sns_topic.alerts.arn]
  insufficient_data_actions = []

  metric_query {
    id          = "e1"
    expression  = "ANOMALY_DETECTION_BAND(m1, 2)"
    label       = "CTR Anomaly Band"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "ctr"
      namespace   = var.project_name
      period      = 300
      stat        = "Average"
    }
    return_data = true
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-ctr-anomaly"
  }
}

# ── EventBridge: Scheduled Offline Evaluation ──
resource "aws_cloudwatch_event_rule" "daily_evaluation" {
  name                = "${var.project_name}-${var.environment}-daily-evaluation"
  description         = "Trigger daily offline evaluation job"
  schedule_expression = "cron(0 3 * * ? *)" # Every day at 03:00 UTC
}

resource "aws_cloudwatch_event_target" "daily_evaluation" {
  rule      = aws_cloudwatch_event_rule.daily_evaluation.name
  target_id = "GlueEvaluationJob"
  arn       = "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:job/${var.evaluation_job_name}"
  role_arn  = var.eventbridge_role_arn
}

# ── Lambda: Metric Publisher (placeholder, deploy separately) ──
# In production, build and deploy Lambda separately via CI/CD
# resource "aws_lambda_function" "metric_publisher" {
#   function_name = "${var.project_name}-${var.environment}-metric-publisher"
#   role          = var.lambda_role_arn
#   handler       = "metric_publisher.handler"
#   runtime       = "python3.11"
#   timeout       = 60
#   memory_size   = 256
#
#   filename         = "lambda_metric_publisher.zip"
#   source_code_hash = filebase64sha256("lambda_metric_publisher.zip")
#
#   environment {
#     variables = {
#       CLOUDWATCH_NAMESPACE = var.project_name
#       ENVIRONMENT          = var.environment
#     }
#   }
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-metric-publisher"
#   }
# }

# ── EventBridge: Metric Publisher Trigger (optional, deploy after Lambda) ──
# resource "aws_cloudwatch_event_rule" "metric_publisher_schedule" {
#   name                = "${var.project_name}-${var.environment}-metric-publisher"
#   description         = "Publish business metrics every 5 minutes"
#   schedule_expression = "rate(5 minutes)"
# }
#
# resource "aws_cloudwatch_event_target" "metric_publisher_schedule" {
#   rule      = aws_cloudwatch_event_rule.metric_publisher_schedule.name
#   target_id = "LambdaTarget"
#   arn       = aws_lambda_function.metric_publisher.arn
# }
#
# resource "aws_lambda_permission" "metric_publisher_eventbridge" {
#   statement_id  = "AllowExecutionFromEventBridge"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.metric_publisher.function_name
#   principal     = "events.amazonaws.com"
#   source_arn    = aws_cloudwatch_event_rule.metric_publisher_schedule.arn
# }

# ── Data Sources ──
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
