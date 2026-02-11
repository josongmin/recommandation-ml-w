# ══════════════════════════════════════════════════════════════════════════════
# Model Training Module (Week 11-12)
# - SageMaker Training Jobs (BPR, LightGCN, Two-Tower, DeepFM)
# - Model Registry (S3 + DynamoDB metadata)
# - Hyperparameter Tuning (Optuna + SageMaker HPO)
# ══════════════════════════════════════════════════════════════════════════════

# ── S3: Model Registry Bucket ──
resource "aws_s3_bucket" "models" {
  bucket = "${var.project_name}-${var.environment}-models"

  tags = {
    Name = "${var.project_name}-${var.environment}-models"
  }
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ── DynamoDB: Model Metadata Table ──
resource "aws_dynamodb_table" "model_metadata" {
  name         = "${var.project_name}-${var.environment}-model-metadata"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "model_id"
  range_key    = "version"

  attribute {
    name = "model_id"
    type = "S"
  }

  attribute {
    name = "version"
    type = "S"
  }

  attribute {
    name = "model_type"
    type = "S"
  }

  attribute {
    name = "is_production"
    type = "S"
  }

  global_secondary_index {
    name            = "model_type_index"
    hash_key        = "model_type"
    range_key       = "version"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "production_index"
    hash_key        = "is_production"
    range_key       = "model_type"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-model-metadata"
  }
}

# ── SageMaker Training Job: BPR ──
resource "aws_sagemaker_notebook_instance" "training" {
  name          = "${var.project_name}-${var.environment}-training-notebook"
  instance_type = "ml.t3.medium"
  role_arn      = var.sagemaker_role_arn

  tags = {
    Name = "${var.project_name}-${var.environment}-training-notebook"
  }
}

# ── ECR: Training Container Images ──
resource "aws_ecr_repository" "training_bpr" {
  name = "${var.project_name}-${var.environment}-training-bpr"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-training-bpr"
  }
}

resource "aws_ecr_repository" "training_lightgcn" {
  name = "${var.project_name}-${var.environment}-training-lightgcn"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-training-lightgcn"
  }
}

resource "aws_ecr_repository" "training_two_tower" {
  name = "${var.project_name}-${var.environment}-training-two-tower"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-training-two-tower"
  }
}

# ── EventBridge: Weekly Training Schedule ──
resource "aws_cloudwatch_event_rule" "weekly_training" {
  name                = "${var.project_name}-${var.environment}-weekly-training"
  description         = "Trigger weekly model retraining"
  schedule_expression = "cron(0 2 ? * SUN *)" # Every Sunday at 02:00 UTC
}

resource "aws_cloudwatch_event_target" "weekly_training" {
  rule      = aws_cloudwatch_event_rule.weekly_training.name
  target_id = "StepFunctionsTarget"
  arn       = aws_sfn_state_machine.training_pipeline.arn
  role_arn  = var.eventbridge_role_arn
}

# ── Step Functions: Training Pipeline ──
resource "aws_sfn_state_machine" "training_pipeline" {
  name     = "${var.project_name}-${var.environment}-training-pipeline"
  role_arn = var.step_functions_role_arn

  definition = jsonencode({
    Comment = "Weekly model training: Dataset → Train → Evaluate → Register"
    StartAt = "BuildDataset"
    States = {
      BuildDataset = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = var.dataset_builder_job_name
        }
        Next = "TrainModels"
      }
      TrainModels = {
        Type = "Parallel"
        Branches = [
          {
            StartAt = "TrainBPR"
            States = {
              TrainBPR = {
                Type     = "Task"
                Resource = "arn:aws:states:::sagemaker:createTrainingJob.sync"
                Parameters = {
                  TrainingJobName = "bpr-training-job"
                  AlgorithmSpecification = {
                    TrainingImage     = "${aws_ecr_repository.training_bpr.repository_url}:latest"
                    TrainingInputMode = "File"
                  }
                  RoleArn = var.sagemaker_role_arn
                  OutputDataConfig = {
                    S3OutputPath = "s3://${aws_s3_bucket.models.bucket}/bpr/"
                  }
                  ResourceConfig = {
                    InstanceType   = "ml.p3.2xlarge"
                    InstanceCount  = 1
                    VolumeSizeInGB = 30
                  }
                  StoppingCondition = {
                    MaxRuntimeInSeconds = 3600
                  }
                }
                End = true
              }
            }
          },
          {
            StartAt = "TrainLightGCN"
            States = {
              TrainLightGCN = {
                Type     = "Task"
                Resource = "arn:aws:states:::sagemaker:createTrainingJob.sync"
                Parameters = {
                  TrainingJobName = "lightgcn-training-job"
                  AlgorithmSpecification = {
                    TrainingImage     = "${aws_ecr_repository.training_lightgcn.repository_url}:latest"
                    TrainingInputMode = "File"
                  }
                  RoleArn = var.sagemaker_role_arn
                  OutputDataConfig = {
                    S3OutputPath = "s3://${aws_s3_bucket.models.bucket}/lightgcn/"
                  }
                  ResourceConfig = {
                    InstanceType   = "ml.p3.2xlarge"
                    InstanceCount  = 1
                    VolumeSizeInGB = 30
                  }
                  StoppingCondition = {
                    MaxRuntimeInSeconds = 7200
                  }
                }
                End = true
              }
            }
          }
        ]
        Next = "RegisterModels"
      }
      RegisterModels = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.model_registry.function_name
          Payload = {
            action = "register_models"
          }
        }
        End = true
      }
    }
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-training-pipeline"
  }
}

# ── Lambda: Model Registry ──
# Note: Deploy Lambda code separately via CI/CD before terraform apply
# Build command: just build-lambda-training
resource "aws_lambda_function" "model_registry" {
  function_name = "${var.project_name}-${var.environment}-model-registry"
  role          = var.lambda_role_arn
  handler       = "model_registry_handler.handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  # Use deployment package variable (build separately)
  filename         = var.lambda_deployment_package
  source_code_hash = filebase64sha256(var.lambda_deployment_package)

  environment {
    variables = {
      MODEL_BUCKET   = aws_s3_bucket.models.bucket
      METADATA_TABLE = aws_dynamodb_table.model_metadata.name
      ENVIRONMENT    = var.environment
    }
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-model-registry"
  }
}
