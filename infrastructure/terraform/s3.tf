# S3 bucket for storing inference results
resource "aws_s3_bucket" "inference_results" {
  bucket = "${var.cluster_name}-inference-results-${random_id.suffix.hex}"

  tags = {
    Name        = "${var.cluster_name}-inference-results"
    Environment = var.environment
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "inference_results" {
  bucket = aws_s3_bucket.inference_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versioning disabled for cost optimization
resource "aws_s3_bucket_versioning" "inference_results" {
  bucket = aws_s3_bucket.inference_results.id

  versioning_configuration {
    status = "Disabled"
  }
}

# Lifecycle rule to delete old objects (cost optimization)
resource "aws_s3_bucket_lifecycle_configuration" "inference_results" {
  bucket = aws_s3_bucket.inference_results.id

  rule {
    id     = "delete-old-annotations"
    status = "Enabled"

    filter {} # REQUIRED (applies to all objects)

    expiration {
      days = 7
    }
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "inference_results" {
  bucket = aws_s3_bucket.inference_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Output S3 bucket details
output "s3_bucket_name" {
  description = "Name of the S3 bucket for inference results"
  value       = aws_s3_bucket.inference_results.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.inference_results.arn
}

output "s3_bucket_region" {
  description = "Region of the S3 bucket"
  value       = aws_s3_bucket.inference_results.region
}
