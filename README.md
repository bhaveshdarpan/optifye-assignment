# optifye-assignment

A small sample project demonstrating a microservice pipeline with publisher, consumer and inference services,
plus AWS-focused infrastructure (EKS, MSK, S3) and Kubernetes deployment manifests.

**Services**

- **Publisher:** publishes frames/messages (services/frame-publisher)
- **Consumer:** consumes frames and forwards for inference (services/consumer-service)
- **Inference:** runs model inference (services/inference-service)

**Quick Start (local)**

- **Prereqs:** `docker`, `python3`, `kubectl` (for Kubernetes), `terraform` and AWS CLI if deploying infra.
- **Run a service directly:**
  - `python services/frame-publisher/publisher.py`
  - `python services/consumer-service/consumer.py`
  - `python services/inference-service/app.py`
- **Build Docker images:**
  - `docker build -t frame-publisher:local services/frame-publisher`
  - `docker build -t consumer-service:local services/consumer-service`
  - `docker build -t inference-service:local services/inference-service`

**Deploy to Kubernetes**

- The repository contains Kubernetes manifests under `infrastructure/kubernetes`.
- Use the included deployment script for convenience: [scripts/deploy-k8s.ps1](scripts/deploy-k8s.ps1) (PowerShell).

**Infrastructure**

- Terraform configs are in `infrastructure/terraform` and include EKS, MSK and S3 resources.
- `terraform.tfvars` holds environment-specific values; do not commit secrets to version control.

**Useful files**

- `services/frame-publisher` - publisher implementation and Dockerfile
- `services/consumer-service` - consumer implementation and Dockerfile
- `services/inference-service` - inference API and Dockerfile
- `infrastructure/kubernetes` - Kubernetes YAML manifests
- `infrastructure/terraform` - Terraform configs for AWS resources

**Notes**

- This README is intentionally short. For environment-specific deploy steps (AWS creds, region, terraform backend), consult the Terraform files and `scripts/deploy-k8s.ps1` before running.
- If you want, I can add a `Makefile` or `docker-compose` for easier local runs.
