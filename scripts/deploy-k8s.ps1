# .\scripts\deploy-k8s.ps1
param (
    [string]$RtspServerIp
)

Write-Host "=== Kubernetes Deployment Script ===" -ForegroundColor Cyan

# ----------------------------
# Pre-flight checks
# ----------------------------
$requiredTools = @("aws", "terraform", "kubectl")
foreach ($tool in $requiredTools) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "$tool is not installed or not in PATH"
        exit 1
    }
}

aws sts get-caller-identity | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "AWS credentials not configured"
    exit 1
}

kubectl cluster-info | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "kubectl is not connected to a cluster"
    exit 1
}

# ----------------------------
# Terraform outputs
# ----------------------------
Write-Host "`n=== Fetching Terraform outputs ===" -ForegroundColor Cyan

$accountId      = aws sts get-caller-identity --query Account --output text
$kafkaBootstrap = terraform output -raw kafka_bootstrap_brokers_tls
$s3Bucket       = terraform output -raw s3_bucket_name
$iamRoleArn     = terraform output -raw consumer_service_role_arn

Write-Host "Account ID      : $accountId"
Write-Host "Kafka Bootstrap : $kafkaBootstrap"
Write-Host "S3 Bucket       : $s3Bucket"
Write-Host "IAM Role ARN    : $iamRoleArn"

# ----------------------------
# RTSP input
# ----------------------------
if (-not $RtspServerIp) {
    $RtspServerIp = Read-Host "Enter RTSP Server IP (or localhost for testing)"
}

# ----------------------------
# Manifest processing
# ----------------------------
Write-Host "`n=== Rendering Kubernetes manifests ===" -ForegroundColor Cyan

$files = @(
    "infrastructure/kubernetes/inference-deployment.yaml",
    "infrastructure/kubernetes/consumer-deployment.yaml",
    "infrastructure/kubernetes/publisher-deployment.yaml"
)

foreach ($file in $files) {
    if (-not (Test-Path $file)) {
        Write-Error "Missing file: $file"
        exit 1
    }

    $content = Get-Content $file -Raw

    $content = $content -replace '<ACCOUNT_ID>', $accountId
    $content = $content -replace '<MSK_BOOTSTRAP_SERVERS>', $kafkaBootstrap
    $content = $content -replace '<S3_BUCKET_NAME>', $s3Bucket
    $content = $content -replace '<IAM_ROLE_ARN>', $iamRoleArn
    $content = $content -replace '<RTSP_SERVER_IP>', $RtspServerIp

    if ($content -match '<.*?>') {
        Write-Error "Unresolved placeholders found in $file"
        exit 1
    }

    $outputFile = $file -replace '.yaml', '-final.yaml'
    $content | Set-Content $outputFile

    Write-Host "Rendered: $outputFile" -ForegroundColor Green
}

# ----------------------------
# Apply manifests
# ----------------------------
Write-Host "`n=== Applying Kubernetes manifests ===" -ForegroundColor Cyan

kubectl apply -f infrastructure/kubernetes/inference-deployment-final.yaml
kubectl apply -f infrastructure/kubernetes/consumer-deployment-final.yaml
kubectl apply -f infrastructure/kubernetes/publisher-deployment-final.yaml

# ----------------------------
# Rollout status
# ----------------------------
Write-Host "`n=== Waiting for rollouts ===" -ForegroundColor Cyan

kubectl rollout status deployment/inference-service --timeout=300s
kubectl rollout status deployment/consumer-service --timeout=300s
kubectl rollout status deployment/frame-publisher --timeout=300s

# ----------------------------
# Status
# ----------------------------
Write-Host "`n=== Cluster Status ===" -ForegroundColor Cyan
kubectl get pods
kubectl get svc
kubectl get hpa

Write-Host "`n=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Logs:"
Write-Host "  kubectl logs -f deployment/inference-service"
Write-Host "  kubectl logs -f deployment/consumer-service"
Write-Host "  kubectl logs -f deployment/frame-publisher"
