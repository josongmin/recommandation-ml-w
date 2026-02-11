# ══════════════════════════════════════════════════════════════════════════════
# Serving Module (Week 13-14)
# - ECS Fargate Cluster (multi-recall + 2-stage ranking)
# - Application Load Balancer (ALB)
# - CloudWatch Logging + X-Ray Tracing
# - Auto-scaling (CPU/Memory-based + Target Tracking)
# ══════════════════════════════════════════════════════════════════════════════

# ── ECR: Serving Container Image ──
resource "aws_ecr_repository" "serving" {
  name = "${var.project_name}-${var.environment}-serving"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-serving"
  }
}

# ── ECS: Cluster ──
resource "aws_ecs_cluster" "serving" {
  name = "${var.project_name}-${var.environment}-serving"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-serving"
  }
}

# ── ECS: Task Definition ──
resource "aws_ecs_task_definition" "serving" {
  family                   = "${var.project_name}-${var.environment}-serving"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.fargate_execution_role_arn
  task_role_arn            = var.fargate_task_role_arn

  container_definitions = jsonencode([
    {
      name  = "serving"
      image = "${aws_ecr_repository.serving.repository_url}:latest"

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "MODEL_BUCKET", value = var.model_bucket_name },
        { name = "FEATURE_STORE_TABLE", value = var.feature_store_table },
        { name = "MODEL_METADATA_TABLE", value = var.model_metadata_table },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "AWS_XRAY_DAEMON_ADDRESS", value = "xray-daemon:2000" }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.serving.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "serving"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    },
    {
      name  = "xray-daemon"
      image = "public.ecr.aws/xray/aws-xray-daemon:latest"

      portMappings = [
        {
          containerPort = 2000
          protocol      = "udp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.serving.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "xray"
        }
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-${var.environment}-serving-task"
  }
}

# ── ECS: Service ──
resource "aws_ecs_service" "serving" {
  name            = "${var.project_name}-${var.environment}-serving"
  cluster         = aws_ecs_cluster.serving.id
  task_definition = aws_ecs_task_definition.serving.arn
  desired_count   = var.min_capacity
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.serving.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.serving.arn
    container_name   = "serving"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 120

  depends_on = [aws_lb_listener.serving]

  tags = {
    Name = "${var.project_name}-${var.environment}-serving-service"
  }
}

# ── Security Group: ECS Service ──
resource "aws_security_group" "serving" {
  name        = "${var.project_name}-${var.environment}-serving-sg"
  description = "Security group for serving ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Allow HTTP from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-serving-sg"
  }
}

# ── Application Load Balancer ──
resource "aws_lb" "serving" {
  name               = "${var.project_name}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false
  enable_http2               = true

  tags = {
    Name = "${var.project_name}-${var.environment}-alb"
  }
}

# ── ALB: Target Group ──
resource "aws_lb_target_group" "serving" {
  name        = "${var.project_name}-${var.environment}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30

  tags = {
    Name = "${var.project_name}-${var.environment}-tg"
  }
}

# ── ALB: Listener (HTTP) ──
resource "aws_lb_listener" "serving" {
  load_balancer_arn = aws_lb.serving.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.serving.arn
  }
}

# ── Security Group: ALB ──
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-${var.environment}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound to ECS"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-alb-sg"
  }
}

# ── CloudWatch: Log Group ──
resource "aws_cloudwatch_log_group" "serving" {
  name              = "/ecs/${var.project_name}-${var.environment}-serving"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-${var.environment}-serving-logs"
  }
}

# ── Auto Scaling: Target ──
resource "aws_appautoscaling_target" "serving" {
  max_capacity       = var.max_capacity
  min_capacity       = var.min_capacity
  resource_id        = "service/${aws_ecs_cluster.serving.name}/${aws_ecs_service.serving.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# ── Auto Scaling: CPU-based ──
resource "aws_appautoscaling_policy" "cpu" {
  name               = "${var.project_name}-${var.environment}-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.serving.resource_id
  scalable_dimension = aws_appautoscaling_target.serving.scalable_dimension
  service_namespace  = aws_appautoscaling_target.serving.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# ── Auto Scaling: Memory-based ──
resource "aws_appautoscaling_policy" "memory" {
  name               = "${var.project_name}-${var.environment}-memory-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.serving.resource_id
  scalable_dimension = aws_appautoscaling_target.serving.scalable_dimension
  service_namespace  = aws_appautoscaling_target.serving.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = 80.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# ── CloudWatch: Custom Metrics Dashboard ──
resource "aws_cloudwatch_dashboard" "serving" {
  dashboard_name = "${var.project_name}-${var.environment}-serving"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", { stat = "Average" }],
            [".", "MemoryUtilization", { stat = "Average" }]
          ]
          period = 300
          region = data.aws_region.current.name
          title  = "ECS Service Metrics"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", { stat = "Average" }],
            [".", "RequestCount", { stat = "Sum" }],
            [".", "HTTPCode_Target_4XX_Count", { stat = "Sum" }],
            [".", "HTTPCode_Target_5XX_Count", { stat = "Sum" }]
          ]
          period = 300
          region = data.aws_region.current.name
          title  = "ALB Metrics"
        }
      }
    ]
  })
}

# ── CloudWatch: Alarms ──
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 85.0
  alarm_description   = "CPU utilization exceeds 85%"

  dimensions = {
    ClusterName = aws_ecs_cluster.serving.name
    ServiceName = aws_ecs_service.serving.name
  }
}

resource "aws_cloudwatch_metric_alarm" "high_memory" {
  alarm_name          = "${var.project_name}-${var.environment}-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 90.0
  alarm_description   = "Memory utilization exceeds 90%"

  dimensions = {
    ClusterName = aws_ecs_cluster.serving.name
    ServiceName = aws_ecs_service.serving.name
  }
}

resource "aws_cloudwatch_metric_alarm" "high_5xx" {
  alarm_name          = "${var.project_name}-${var.environment}-high-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10.0
  alarm_description   = "5XX errors exceed threshold"

  dimensions = {
    LoadBalancer = aws_lb.serving.arn_suffix
  }
}

# ── Data: Current Region ──
data "aws_region" "current" {}
