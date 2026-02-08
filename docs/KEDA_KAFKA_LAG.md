# KEDA: Autoscale inference on Kafka lag (BONUS)

The inference Deployment can be scaled based on **Kafka consumer group lag** so that when the `video-frames` topic has backlog, more inference replicas are scheduled and the consumer can process batches faster.

## How it works

- **KEDA** (Kubernetes Event-Driven Autoscaling) runs in the cluster and evaluates the Kafka trigger periodically.
- It reads the **consumer group lag** for `inference-consumer-group` on topic `video-frames` by connecting to MSK (TLS port).
- A **ScaledObject** targets the `inference-service` Deployment: when lag exceeds `lagThreshold`, KEDA scales the deployment up (up to `maxReplicaCount`); when lag is low, it scales down to `minReplicaCount`.

## Prerequisites

- MSK and EKS already deployed (Terraform applied).
- `kubectl` configured for the EKS cluster.

## Install KEDA

Install KEDA in the cluster (once per cluster):

```bash
# Add KEDA Helm repo and install
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda -n keda --create-namespace
```

Or use the official manifests: <https://github.com/kedacore/keda/releases>.

## Deploy the ScaledObject

The ScaledObject is in `infrastructure/kubernetes/keda-inference-scaledobject.yaml` and uses the placeholder `<MSK_BOOTSTRAP_SERVERS>`. Either:

1. **Use the deploy script** (from repo root):  
   `.\scripts\deploy-k8s.ps1`  
   It substitutes Terraform outputs and writes `keda-inference-scaledobject-final.yaml`, then applies it.

2. **Or substitute manually** and apply:
   - Replace `<MSK_BOOTSTRAP_SERVERS>` with the TLS bootstrap brokers (e.g. `terraform output -raw kafka_bootstrap_brokers_tls` from `infrastructure/terraform`).
   - `kubectl apply -f infrastructure/kubernetes/keda-inference-scaledobject.yaml`

## Coexistence with CPU HPA

The default inference manifest also defines a **CPU-based HPA** (`inference-service-hpa`). Having both KEDA (lag-based) and CPU HPA on the same Deployment can conflict. Options:

- **Recommended when using KEDA:** Remove or comment out the `HorizontalPodAutoscaler` block for `inference-service-hpa` in `infrastructure/kubernetes/inference-deployment.yaml`, then re-run the deploy script so only KEDA controls inference replicas.
- Or keep the CPU HPA and do not apply the KEDA ScaledObject; inference will then scale only on CPU.

## MSK and TLS

MSK is configured with **TLS in transit** (no SASL). The ScaledObject uses:

- `tls: enable` so KEDA connects to brokers on the TLS port (9094).
- `unsafeSsl: "true"` to skip server certificate verification (matching the consumer’s `CERT_NONE` behavior). For production you would configure a proper CA/cert instead.

KEDA runs on EKS nodes that can reach MSK (same VPC); no extra IAM or MSK IAM auth is required for this TLS-only setup.

## Parameters

- **lagThreshold:** `"5"` – scale when total lag (across partitions) is above 5 messages.
- **minReplicaCount / maxReplicaCount:** 1 and 10 – inference replicas stay within this range.
- **pollingInterval:** 30 seconds.

Adjust these in `keda-inference-scaledobject.yaml` as needed.
