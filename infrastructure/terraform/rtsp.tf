data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }
}

resource "aws_security_group" "rtsp" {
  name_prefix = "${var.cluster_name}-rtsp-"
  description = "RTSP server for demo video stream"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 8554
    to_port     = 8554
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
    description = "RTSP from VPC"
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
    Name = "${var.cluster_name}-rtsp-sg"
  }
}

resource "aws_security_group_rule" "eks_to_rtsp" {
  type                     = "ingress"
  from_port                = 8554
  to_port                  = 8554
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rtsp.id # The RTSP SG
  source_security_group_id = aws_security_group.eks_nodes.id # The EKS SG
  description              = "Allow EKS nodes to reach RTSP server"
}

locals {
  rtsp_user_data = <<-EOT
#!/bin/bash
set -e
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker

mkdir -p /media /opt/rtsp

curl -sL -o /media/video.mp4 "https://www.w3schools.com/html/mov_bbb.mp4"

cat > /opt/rtsp/rtsp-simple-server.yml << 'CONFIG'
paths:
  media:
    source: file:///media/video.mp4
    runOnInit: loop         
    runOnInitRestart: yes   
CONFIG

docker run -d --restart unless-stopped --name rtsp \
  -p 8554:8554 \
  -v /media:/media \
  -v /opt/rtsp/rtsp-simple-server.yml:/rtsp-simple-server.yml \
  aler9/rtsp-simple-server
EOT
}

resource "aws_instance" "rtsp" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type           = var.rtsp_instance_type
  subnet_id               = module.vpc.public_subnets[0]
  vpc_security_group_ids  = [aws_security_group.rtsp.id]
  user_data               = local.rtsp_user_data
  user_data_replace_on_change = true
  associate_public_ip_address = true

  tags = {
    Name = "${var.cluster_name}-rtsp-server"
  }
}

output "rtsp_server_private_ip" {
  description = "Private IP of RTSP server (use for publisher in same VPC)"
  value       = aws_instance.rtsp.private_ip
}

output "rtsp_server_public_ip" {
  description = "Public IP of RTSP server (use if publisher is outside VPC)"
  value       = aws_instance.rtsp.public_ip
}

output "rtsp_url_private" {
  description = "RTSP URL using private IP (for frame-publisher in EKS)"
  value       = "rtsp://${aws_instance.rtsp.private_ip}:8554/media"
}

output "rtsp_url_public" {
  description = "RTSP URL using public IP"
  value       = "rtsp://${aws_instance.rtsp.public_ip}:8554/media"
}
