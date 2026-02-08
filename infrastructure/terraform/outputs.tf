# Consolidated outputs for easy reference

output "region" {
  description = "AWS region"
  value       = var.aws_region
}

output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = var.cluster_name
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}

# Summary output for easy copy-paste
output "deployment_summary" {
  description = "Summary of deployed resources"
  value       = <<-EOT
  
  ================================
  DEPLOYMENT SUMMARY
  ================================
  
  Region: ${var.aws_region}
  Cluster: ${var.cluster_name}
  
  KAFKA (MSK):
  - Bootstrap Servers: ${aws_msk_cluster.main.bootstrap_brokers}
  
  KUBERNETES (EKS):
  - Cluster Name: ${module.eks.cluster_name}
  - Endpoint: ${module.eks.cluster_endpoint}
  - Configure kubectl: aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}
  
  S3:
  - Bucket: ${aws_s3_bucket.inference_results.id}
  - Region: ${aws_s3_bucket.inference_results.region}
  
  IAM:
  - Consumer Service Role ARN: ${module.s3_irsa_role.iam_role_arn}
  
  NEXT STEPS:
  1. Configure kubectl: aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}
  2. Update Kubernetes manifests with:
     - KAFKA_BOOTSTRAP: ${aws_msk_cluster.main.bootstrap_brokers}
     - S3_BUCKET: ${aws_s3_bucket.inference_results.id}
     - IAM_ROLE_ARN: ${module.s3_irsa_role.iam_role_arn}
  3. Deploy applications to EKS
  
  ================================
  EOT
}
