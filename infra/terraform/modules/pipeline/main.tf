# ══════════════════════════════════════════════════════════════════════════════
# Batch Pipeline Module (Week 5-8)
# - Glue Jobs (Bronze → Silver → Gold-A → Gold-B → Dataset)
# - Step Functions Workflow (Daily orchestration)
# - EventBridge Schedule (Daily trigger)
# ══════════════════════════════════════════════════════════════════════════════

# ── Glue Job: Bronze → Silver ──
resource "aws_glue_job" "bronze_to_silver" {
  name     = "${var.project_name}-${var.environment}-bronze-to-silver"
  role_arn = var.glue_role_arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_bucket_name}/glue-scripts/bronze_to_silver.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"          = "python"
    "--enable-metrics"        = "true"
    "--enable-spark-ui"       = "true"
    "--spark-event-logs-path" = "s3://${var.s3_bucket_name}/glue-logs/"
    "--extra-py-files"        = "s3://${var.s3_bucket_name}/packages/wine_rec.zip"
    "--TempDir"               = "s3://${var.s3_bucket_name}/glue-temp/"
  }

  max_retries       = 1
  timeout           = 60 # minutes
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
}

# ── Glue Job: Silver → Gold-A ──
resource "aws_glue_job" "silver_to_gold_a" {
  name     = "${var.project_name}-${var.environment}-silver-to-gold-a"
  role_arn = var.glue_role_arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_bucket_name}/glue-scripts/silver_to_gold_a.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"   = "python"
    "--enable-metrics" = "true"
    "--extra-py-files" = "s3://${var.s3_bucket_name}/packages/wine_rec.zip"
    "--TempDir"        = "s3://${var.s3_bucket_name}/glue-temp/"
  }

  max_retries       = 1
  timeout           = 60
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
}

# ── Glue Job: Gold-A → Gold-B ──
resource "aws_glue_job" "gold_a_to_gold_b" {
  name     = "${var.project_name}-${var.environment}-gold-a-to-gold-b"
  role_arn = var.glue_role_arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_bucket_name}/glue-scripts/gold_a_to_gold_b.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"   = "python"
    "--enable-metrics" = "true"
    "--extra-py-files" = "s3://${var.s3_bucket_name}/packages/wine_rec.zip"
    "--TempDir"        = "s3://${var.s3_bucket_name}/glue-temp/"
  }

  max_retries       = 1
  timeout           = 60
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
}

# ── Glue Job: Dataset Builder ──
resource "aws_glue_job" "dataset_builder" {
  name     = "${var.project_name}-${var.environment}-dataset-builder"
  role_arn = var.glue_role_arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_bucket_name}/glue-scripts/dataset_builder.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"   = "python"
    "--enable-metrics" = "true"
    "--extra-py-files" = "s3://${var.s3_bucket_name}/packages/wine_rec.zip"
    "--TempDir"        = "s3://${var.s3_bucket_name}/glue-temp/"
  }

  max_retries       = 1
  timeout           = 90
  glue_version      = "4.0"
  worker_type       = "G.2X"
  number_of_workers = 3
}

# ── Step Functions: Daily Pipeline Workflow ──
resource "aws_sfn_state_machine" "daily_pipeline" {
  name     = "${var.project_name}-${var.environment}-daily-pipeline"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode({
    Comment = "Daily ETL: Bronze → Silver → Gold-A → Gold-B → Dataset"
    StartAt = "BronzeToSilver"
    States = {
      BronzeToSilver = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.bronze_to_silver.name
          Arguments = {
            "--dt.$" = "$.dt"
          }
        }
        ResultPath = "$.glueResult"
        Next       = "SilverToGoldA"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "FailureNotification"
        }]
      }
      SilverToGoldA = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.silver_to_gold_a.name
          Arguments = {
            "--dt.$" = "$.dt"
          }
        }
        ResultPath = "$.glueResult"
        Next       = "GoldAToGoldB"
      }
      GoldAToGoldB = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.gold_a_to_gold_b.name
          Arguments = {
            "--dt.$" = "$.dt"
          }
        }
        ResultPath = "$.glueResult"
        Next       = "DatasetBuilder"
      }
      DatasetBuilder = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.dataset_builder.name
          Arguments = {
            "--dt.$" = "$.dt"
          }
        }
        ResultPath = "$.glueResult"
        Next       = "Success"
      }
      Success = {
        Type = "Succeed"
      }
      FailureNotification = {
        Type  = "Fail"
        Cause = "Glue job failed"
      }
    }
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-daily-pipeline"
  }
}

# ── IAM Role: Step Functions ──
resource "aws_iam_role" "step_functions" {
  name = "${var.project_name}-${var.environment}-stepfunctions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "step_functions_glue" {
  name = "glue-access"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "glue:StartJobRun",
        "glue:GetJobRun",
        "glue:GetJobRuns",
        "glue:BatchStopJobRun"
      ]
      Resource = "*"
    }]
  })
}

# ── EventBridge Schedule: Daily 01:00 UTC ──
resource "aws_cloudwatch_event_rule" "daily_pipeline" {
  name                = "${var.project_name}-${var.environment}-daily-pipeline"
  description         = "Trigger daily ETL pipeline at 01:00 UTC"
  schedule_expression = "cron(0 1 * * ? *)"
}

resource "aws_cloudwatch_event_target" "daily_pipeline" {
  rule      = aws_cloudwatch_event_rule.daily_pipeline.name
  target_id = "StepFunctionsTarget"
  arn       = aws_sfn_state_machine.daily_pipeline.arn
  role_arn  = aws_iam_role.eventbridge.arn

  input = jsonencode({
    dt = "$${date}"
  })
}

# ── IAM Role: EventBridge → Step Functions ──
resource "aws_iam_role" "eventbridge" {
  name = "${var.project_name}-${var.environment}-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_sfn" {
  name = "stepfunctions-access"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "states:StartExecution"
      Resource = aws_sfn_state_machine.daily_pipeline.arn
    }]
  })
}
