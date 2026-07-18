terraform {
  required_version = ">= 1.5.0"
}

module "deployment_shape" {
  source      = "../../modules/deployment_shape"
  environment = "production"
  region      = "reference-region"

  container_service = {
    name                      = "aegis-production-runtime"
    desired_count             = 3
    cpu                       = "4 vCPU"
    memory                    = "16 GiB"
    restricted_worker_egress  = true
    graceful_shutdown_seconds = 90
  }

  postgres = {
    engine                = "managed-postgresql"
    version               = "16"
    private               = true
    high_availability     = true
    backup_retention_days = 35
    deletion_protection   = true
  }

  redis = {
    engine         = "managed-redis-compatible"
    version        = "7"
    private        = true
    tls_required   = true
    backup_enabled = true
  }

  object_storage = {
    kind       = "managed-object-storage"
    private    = true
    encryption = "customer-managed-key"
    versioning = true
  }

  secret_references = [
    "postgres/password",
    "redis/auth-token",
    "object-storage/access-key",
    "object-storage/secret-key",
    "oidc/client-secret",
    "edge/tls-certificate",
    "telemetry/otlp-endpoint",
  ]

  network = {
    name                           = "aegis-production-network"
    private_data_subnets           = true
    data_ingress_from_runtime_only = true
    tls_termination_at_edge        = true
    worker_egress_allowlist        = ["approved-provider-endpoints"]
  }

  edge = {
    https_only               = true
    certificate_reference    = "secret-manager:edge/tls-certificate"
    dns_managed_outside_repo = true
  }

  telemetry = {
    otlp_endpoint_reference = "secret-manager:telemetry/otlp-endpoint"
    logs                    = true
    metrics                 = true
    traces                  = true
  }

  backups = {
    postgres_schedule          = "continuous-plus-daily-snapshot"
    object_storage_sync        = "provider-versioned-cross-account-sync"
    restore_rehearsal_required = true
  }
}
