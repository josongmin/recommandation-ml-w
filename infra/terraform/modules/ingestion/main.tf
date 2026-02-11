# ══════════════════════════════════════════════════════════════════════════════
# Ingestion Module (Week 3-4)
# - API Gateway HTTP API
# - Kinesis Data Stream (On-demand)
# - Lambda (event validation)
# - Kinesis Firehose → S3 Bronze
# ══════════════════════════════════════════════════════════════════════════════

# ── Kinesis Data Stream ──
resource "aws_kinesis_stream" "events" {
  name = "${var.project_name}-${var.environment}-events-stream"
  stream_mode_details {
    stream_mode = "ON_DEMAND"
  }

  retention_period = 24 # hours

  tags = {
    Name = "${var.project_name}-${var.environment}-events-stream"
  }
}

# ── Lambda: Event Validator ──
resource "aws_lambda_function" "validator" {
  function_name = "${var.project_name}-${var.environment}-event-validator"
  role          = var.lambda_role_arn
  handler       = "wine_rec.ingestion.lambda_handler.handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  environment {
    variables = {
      KINESIS_STREAM_NAME = aws_kinesis_stream.events.name
      ENVIRONMENT         = var.environment
    }
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-event-validator"
  }
}

resource "aws_cloudwatch_log_group" "validator_logs" {
  name              = "/aws/lambda/${aws_lambda_function.validator.function_name}"
  retention_in_days = 7
}

# ── API Gateway HTTP API ──
resource "aws_apigatewayv2_api" "http" {
  name          = "${var.project_name}-${var.environment}-ingestion-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type", "x-api-key"]
    max_age       = 300
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-ingestion-api"
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}-ingestion"
  retention_in_days = 7
}

# ── API Gateway → Lambda Integration ──
resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.http.id
  integration_type = "AWS_PROXY"

  integration_uri        = aws_lambda_function.validator.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "post_events" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /events"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.validator.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

# ── Kinesis Firehose → S3 Bronze ──
resource "aws_kinesis_firehose_delivery_stream" "bronze" {
  name        = "${var.project_name}-${var.environment}-bronze-delivery"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.events.arn
    role_arn           = aws_iam_role.firehose.arn
  }

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose.arn
    bucket_arn = var.s3_bucket_arn

    prefix              = "bronze/dt=!{timestamp:yyyy-MM-dd}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/dt=!{timestamp:yyyy-MM-dd}/"

    buffering_size     = 64  # MB (minimum for Parquet conversion)
    buffering_interval = 300 # seconds (5 minutes)

    compression_format = "UNCOMPRESSED"

    data_format_conversion_configuration {
      input_format_configuration {
        deserializer {
          open_x_json_ser_de {}
        }
      }

      output_format_configuration {
        serializer {
          parquet_ser_de {
            compression = "SNAPPY"
          }
        }
      }

      schema_configuration {
        database_name = var.glue_catalog_database
        table_name    = "event_logs_v1"
        role_arn      = aws_iam_role.firehose.arn
      }
    }

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose_logs.name
      log_stream_name = "S3Delivery"
    }
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-bronze-delivery"
  }
}

resource "aws_cloudwatch_log_group" "firehose_logs" {
  name              = "/aws/kinesisfirehose/${var.project_name}-${var.environment}-bronze"
  retention_in_days = 7
}

# ── IAM: Firehose Role ──
resource "aws_iam_role" "firehose" {
  name = "${var.project_name}-${var.environment}-firehose-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "firehose.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "firehose_s3" {
  name = "s3-access"
  role = aws_iam_role.firehose.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kinesis:DescribeStream",
          "kinesis:GetShardIterator",
          "kinesis:GetRecords",
          "kinesis:ListShards"
        ]
        Resource = aws_kinesis_stream.events.arn
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetTable",
          "glue:GetTableVersion",
          "glue:GetTableVersions"
        ]
        Resource = [
          "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:catalog",
          "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:database/${var.glue_catalog_database}",
          "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.glue_catalog_database}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.firehose_logs.arn}:*"
      }
    ]
  })
}
