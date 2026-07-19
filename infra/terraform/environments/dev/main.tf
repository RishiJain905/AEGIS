terraform {
  required_version = ">= 1.5.0"
}

module "deployment_shape" {
  source      = "../../modules/deployment_shape"
  environment = "dev"
  region      = "local"

  container_service = {
    name                      = "aegis-local-runtime"
    desired_count             = 1
    cpu                       = "2 vCPU"
    memory                    = "4 GiB"
    restricted_worker_egress  = true
    graceful_shutdown_seconds = 30
  }

  postgres = {
    engine                = "postgresql"
    version               = "16"
    private               = true
    high_availability     = false
    backup_retention_days = 1
    deletion_protection   = false
  }

  redis = {
    engine         = "redis-compatible"
    version        = "7"
    private        = true
    tls_required   = false
    backup_enabled = false
  }

  object_storage = {
    kind       = "s3-compatible-local-minio"
    private    = true
    encryption = "local-volume"
    versioning = true
  }

  secret_references = [
    "postgres/password",
    "object-storage/access-key",
    "object-storage/secret-key",
    "oidc/client-secret",
  ]

  network = {
    name                           = "aegis-local-network"
    private_data_subnets           = true
    data_ingress_from_runtime_only = true
    tls_termination_at_edge        = false
    worker_egress_allowlist        = ["mock-provider-only"]
  }

  edge = {
    https_only               = false
    certificate_reference    = "local-only"
    dns_managed_outside_repo = true
  }

  telemetry = {
    otlp_endpoint_reference = "otel-collector:4317"
    logs                    = true
    metrics                 = true
    traces                  = true
  }

  backups = {
    postgres_schedule          = "on-demand-local-rehearsal"
    object_storage_sync        = "documented-only"
    restore_rehearsal_required = true
  }
}
