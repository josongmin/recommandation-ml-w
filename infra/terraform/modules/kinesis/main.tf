# Kinesis Data Stream for event ingestion (RFC-INFRA-IMPL-013)

variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "stream_name" {
  type    = string
  default = "wine-events-stream"
}

resource "aws_kinesis_stream" "events" {
  name             = "${var.project}-${var.env}-${var.stream_name}"
  retention_period = 24 # hours

  stream_mode_details {
    stream_mode = "ON_DEMAND"
  }
}

output "stream_name" {
  value = aws_kinesis_stream.events.name
}

output "stream_arn" {
  value = aws_kinesis_stream.events.arn
}
