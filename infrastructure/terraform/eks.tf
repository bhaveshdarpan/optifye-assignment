data "aws_caller_identity" "current" {}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.16"

  cluster_name    = var.cluster_name
  cluster_version = "1.32"

  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnets
  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    inference_nodes = {
      name = "${var.cluster_name}-nodes"

      instance_types = [var.eks_node_instance_type]
      capacity_type  = "SPOT"

      min_size     = var.eks_min_capacity
      max_size     = var.eks_max_capacity
      desired_size = var.eks_desired_capacity

      labels = {
        role        = "inference"
        environment = var.environment
      }

      taints                 = []
      vpc_security_group_ids = [aws_security_group.eks_nodes.id]

      tags = {
        Name = "${var.cluster_name}-node"
      }
    }
  }

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
  }

  tags = {
    Name = var.cluster_name
  }
}

resource "aws_eks_access_entry" "admin" {
  cluster_name  = module.eks.cluster_name
  principal_arn = data.aws_caller_identity.current.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "admin_policy" {
  cluster_name  = module.eks.cluster_name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  principal_arn = aws_eks_access_entry.admin.principal_arn

  access_scope {
    type = "cluster"
  }
}

resource "aws_security_group" "eks_nodes" {
  name_prefix = "${var.cluster_name}-eks-nodes-"
  description = "Security group for EKS worker nodes"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    self        = true
    description = "Allow node to node communication"
  }

  ingress {
    from_port       = 9092
    to_port         = 9092
    protocol        = "tcp"
    security_groups = [aws_security_group.msk.id]
    description     = "Allow Kafka access"
  }

  ingress {
    from_port       = 9094
    to_port         = 9094
    protocol        = "tcp"
    security_groups = [aws_security_group.msk.id]
    description     = "Allow Kafka TLS access"
  }

  ingress {
    from_port   = 8554
    to_port     = 8554
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
    description = "Allow RTSP traffic from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${var.cluster_name}-eks-nodes-sg"
  }
}

module "s3_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.30"

  role_name = "${var.cluster_name}-consumer-s3-access"

  role_policy_arns = {
    s3_policy = aws_iam_policy.s3_access.arn
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["default:consumer-sa"]
    }
  }

  tags = {
    Name = "${var.cluster_name}-consumer-s3-role"
  }
}

resource "aws_iam_policy" "s3_access" {
  name_prefix = "${var.cluster_name}-s3-access-"
  description = "Policy for consumer service to access S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.inference_results.arn,
          "${aws_s3_bucket.inference_results.arn}/*"
        ]
      }
    ]
  })
}

output "eks_cluster_id" {
  description = "EKS cluster ID"
  value       = module.eks.cluster_id
}

output "eks_cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_oidc_provider_arn" {
  description = "ARN of the OIDC Provider for EKS"
  value       = module.eks.oidc_provider_arn
}

output "consumer_service_role_arn" {
  description = "IAM role ARN for consumer service"
  value       = module.s3_irsa_role.iam_role_arn
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
