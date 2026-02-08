param (
    [string]$RtspServerIp
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Get-Item $scriptDir).Parent.FullName
if ((Get-Location).Path -ne $repoRoot) {
    Set-Location $repoRoot
    Write-Host "Working directory set to repo root: $repoRoot"
}

Write-Host "=== Kubernetes Deployment Script ===" -ForegroundColor Cyan

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

$terraformDir = if (Test-Path "infrastructure/terraform") { "infrastructure/terraform" } else { "." }
Push-Location $terraformDir
try {
    $kafkaBootstrap = terraform output -raw kafka_bootstrap_brokers_tls
    $s3Bucket       = terraform output -raw s3_bucket_name
    $iamRoleArn     = terraform output -raw consumer_service_role_arn
    $awsRegion      = terraform output -raw region
    $rtspPrivateIp  = terraform output -raw rtsp_server_private_ip 2>$null
} finally {
    Pop-Location
}

$accountId   = aws sts get-caller-identity --query Account --output text
$ecrRegistry = "$accountId.dkr.ecr.$awsRegion.amazonaws.com"

Write-Host "`n=== Fetching Terraform outputs ===" -ForegroundColor Cyan
Write-Host "Account ID      : $accountId"
Write-Host "ECR Registry    : $ecrRegistry"
Write-Host "Kafka Bootstrap : $kafkaBootstrap"
Write-Host "S3 Bucket       : $s3Bucket"
Write-Host "IAM Role ARN    : $iamRoleArn"

if (-not $RtspServerIp) {
    if ($rtspPrivateIp) {
        $RtspServerIp = $rtspPrivateIp
        Write-Host "RTSP Server     : $RtspServerIp (from Terraform)"
    } else {
        $RtspServerIp = Read-Host "Enter RTSP Server IP (or localhost for testing)"
    }
}
$rtspUrl = "rtsp://${RtspServerIp}:8554/media"

$kafkaTopic         = if ($env:KAFKA_TOPIC) { $env:KAFKA_TOPIC } else { "video-frames" }
$kafkaConsumerGroup = if ($env:KAFKA_CONSUMER_GROUP) { $env:KAFKA_CONSUMER_GROUP } else { "inference-consumer-group" }
$inferenceUrl       = if ($env:INFERENCE_URL) { $env:INFERENCE_URL } else { "http://inference-service:8000" }
$batchSize          = if ($env:BATCH_SIZE) { $env:BATCH_SIZE } else { "25" }
$fps                = if ($env:FPS) { $env:FPS } else { "30" }

Write-Host "`n=== Installing KEDA ===" -ForegroundColor Cyan

if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
    Write-Error "helm is not installed or not in PATH. KEDA installation requires Helm."
    exit 1
}

helm repo add kedacore https://kedacore.github.io/charts
helm repo update

$kedaRelease = helm list -n keda 2>$null | Select-String "keda"
if ($kedaRelease) {
    Write-Host "KEDA is already installed, skipping..." -ForegroundColor Yellow
} else {
    Write-Host "Installing KEDA from Helm chart..." -ForegroundColor Cyan
    helm install keda kedacore/keda -n keda --create-namespace
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install KEDA"
        exit 1
    }
    Write-Host "Waiting for KEDA to be ready..." -ForegroundColor Cyan
    kubectl wait --for=condition=available --timeout=300s deployment/keda-operator -n keda
}

Write-Host "`n=== Rendering Kubernetes manifests ===" -ForegroundColor Cyan

$files = @(
    "infrastructure/kubernetes/inference-deployment.yaml",
    "infrastructure/kubernetes/consumer-deployment.yaml",
    "infrastructure/kubernetes/publisher-deployment.yaml",
    "infrastructure/kubernetes/keda-inference-scaledobject.yaml"
)

foreach ($file in $files) {
    if (-not (Test-Path $file)) {
        Write-Warning "Skipping missing file: $file"
        continue
    }

    $content = Get-Content $file -Raw

    $content = $content -replace '<ACCOUNT_ID>', $accountId
    $content = $content -replace '<ECR_REGISTRY>', $ecrRegistry
    $content = $content -replace '<MSK_BOOTSTRAP_SERVERS>', $kafkaBootstrap
    $content = $content -replace '<S3_BUCKET_NAME>', $s3Bucket
    $content = $content -replace '<IAM_ROLE_ARN>', $iamRoleArn
    $content = $content -replace '<RTSP_SERVER_IP>', $RtspServerIp
    $content = $content -replace '<RTSP_URL>', $rtspUrl
    $content = $content -replace '<KAFKA_TOPIC>', $kafkaTopic
    $content = $content -replace '<KAFKA_CONSUMER_GROUP>', $kafkaConsumerGroup
    $content = $content -replace '<INFERENCE_URL>', $inferenceUrl
    $content = $content -replace '<AWS_REGION>', $awsRegion
    $content = $content -replace '<BATCH_SIZE>', $batchSize
    $content = $content -replace '<FPS>', $fps

    if ($content -match '<.*?>') {
        Write-Error "Unresolved placeholders found in $file"
        exit 1
    }

    $outputFile = $file -replace '.yaml', '-final.yaml'
    $content | Set-Content $outputFile

    Write-Host "Rendered: $outputFile" -ForegroundColor Green
}

Write-Host "`n=== Applying Kubernetes manifests ===" -ForegroundColor Cyan

kubectl apply -f infrastructure/kubernetes/inference-deployment-final.yaml
kubectl apply -f infrastructure/kubernetes/consumer-deployment-final.yaml
kubectl apply -f infrastructure/kubernetes/publisher-deployment-final.yaml
if (Test-Path "infrastructure/kubernetes/keda-inference-scaledobject-final.yaml") {
    kubectl delete hpa inference-service-hpa -n default --ignore-not-found=true
    kubectl apply -f infrastructure/kubernetes/keda-inference-scaledobject-final.yaml
}

Write-Host "`n=== Waiting for rollouts ===" -ForegroundColor Cyan

kubectl rollout status deployment/inference-service --timeout=300s
kubectl rollout status deployment/consumer-service --timeout=300s
kubectl rollout status deployment/frame-publisher --timeout=300s

Write-Host "`n=== Cluster Status ===" -ForegroundColor Cyan
kubectl get pods
kubectl get svc
kubectl get hpa

Write-Host "`n=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Logs:"
Write-Host "  kubectl logs -f deployment/inference-service"
Write-Host "  kubectl logs -f deployment/consumer-service"
Write-Host "  kubectl logs -f deployment/frame-publisher"
