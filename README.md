# video-streaming-and-inference

A small sample project demonstrating a microservice pipeline for video/frame streaming and inference,
with Terraform-managed AWS infrastructure and Kubernetes deployment manifests.

**Services (streaming pipeline)**

- **Frame Publisher:** reads video frames and publishes them as messages to a broker (services/frame-publisher).
- **Consumer:** subscribes to the broker, processes/forwards frames and prepares inference requests (services/consumer-service).
- **Inference:** exposes an API that runs model inference on incoming frames (services/inference-service).

These components are intended to work together: the publisher produces frames, the consumer consumes frames and forwards them (or stores them), and the inference service performs model predictions.

**Video streaming service**

- The frame-publisher implements a simple streaming client that captures or reads frames and sends them to the configured topic/endpoint.
- Out-of-the-box this project targets a Kafka-compatible broker (AWS MSK in infra) but can be adapted to other transports.
- Check `services/*/requirements.txt` for Python deps and `Dockerfile` for containerization details.

**Terraform resources (infrastructure/terraform)**

- **EKS:** Managed Kubernetes cluster to run the services.
- **MSK:** Managed Kafka cluster used as the message broker for frame streams.
- **S3:** Object storage for artifacts, model files, or archived frames.
- **Other:** IAM roles, security groups and networking resources required by the above (see `main.tf`, `eks.tf`, `msk.tf`, `s3.tf`).
- `outputs.tf` exposes key values (cluster name, MSK endpoints, S3 buckets) that are useful when templating k8s manifests or CI pipelines.
- Configure your environment in `terraform.tfvars`; do not commit secrets or credentials.

**Kubernetes deployment (infrastructure/kubernetes)**

- Manifests for publisher, consumer and inference services are in `infrastructure/kubernetes` (deployment YAMLs and variations).
- Use `kubectl apply -f infrastructure/kubernetes/` to deploy, or the convenience script: [scripts/deploy-k8s.ps1](scripts/deploy-k8s.ps1).
- Typical workflow:
  1. Provision infra with Terraform (EKS, MSK, S3).
  2. Build and push container images to a registry accessible by the cluster.
  3. Update k8s manifests with image tags and broker endpoints (from Terraform outputs).
  4. Apply manifests to the cluster.

**Configuration**

- No account IDs, broker URLs, or bucket names are hardcoded. All such values come from environment variables or from Terraform/deploy script output.
- For local runs and tests, copy [env.example](env.example) to `.env` and set `KAFKA_BOOTSTRAP`, `S3_BUCKET`, etc. Required in production: `KAFKA_BOOTSTRAP`, `S3_BUCKET` (consumer); `KAFKA_BOOTSTRAP` (publisher).
- CI/CD: set repository variables `AWS_REGION` and `EKS_CLUSTER` (Settings > Secrets and variables > Actions) to override workflow defaults.

**Quick start (local / dev)**

- Prereqs: `docker`, `python3`, `kubectl` (if using k8s), `terraform`, AWS CLI (for cloud deploys).
- Set required env (see [env.example](env.example)); then run services locally:
  - `python services/frame-publisher/publisher.py`
  - `python services/consumer-service/consumer.py`
  - `python services/inference-service/app.py`
- Build Docker images:
  - `docker build -t frame-publisher:local services/frame-publisher`
  - `docker build -t consumer-service:local services/consumer-service`
  - `docker build -t inference-service:local services/inference-service`

**Files of interest**

- `services/frame-publisher` — publisher implementation, `publisher.py` and `Dockerfile`.
- `services/consumer-service` — consumer logic and `Dockerfile`.
- `services/inference-service` — inference API and `Dockerfile`.
- `infrastructure/terraform` — Terraform modules and resource definitions.
- `infrastructure/kubernetes` — Kubernetes manifests and deployment variants.
- `scripts/deploy-k8s.ps1` — convenience script for applying k8s manifests (PowerShell).

**Notes & next steps**

- Before applying Terraform, set AWS credentials and review `terraform.tfvars`.
- Manifests in `infrastructure/kubernetes/*.yaml` use placeholders (`<ECR_REGISTRY>`, `<MSK_BOOTSTRAP_SERVERS>`, etc.). Run [scripts/deploy-k8s.ps1](scripts/deploy-k8s.ps1) from the repo root to substitute Terraform outputs and generate `*-final.yaml` (then apply those). The script reads from `infrastructure/terraform` and optionally uses the RTSP server private IP from Terraform.
- **BONUS – Kafka-lag autoscaling:** To scale the inference Deployment on Kafka consumer lag, install [KEDA](https://keda.sh) and apply the ScaledObject; see [docs/KEDA_KAFKA_LAG.md](docs/KEDA_KAFKA_LAG.md).
