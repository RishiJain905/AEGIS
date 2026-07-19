locals {
  naming = {
    network        = "aegis-${var.environment}-private-network"
    runtime        = "aegis-${var.environment}-runtime"
    postgres       = "aegis-${var.environment}-postgres"
    redis          = "aegis-${var.environment}-redis"
    object_storage = "aegis-${var.environment}-objects"
    secret_manager = "aegis-${var.environment}-secrets"
    edge           = "aegis-${var.environment}-https-edge"
    telemetry      = "aegis-${var.environment}-telemetry"
    backups        = "aegis-${var.environment}-backups"
  }
}

# terraform_data is a built-in Terraform resource. These resources are
# intentionally an offline, provider-neutral inventory of the target shape;
# they do not create cloud resources, contact a provider, or contain secrets.
resource "terraform_data" "network" {
  input = {
    id                             = local.naming.network
    name                           = var.network.name
    private_data_subnets           = var.network.private_data_subnets
    data_ingress_from_runtime_only = var.network.data_ingress_from_runtime_only
    worker_egress_allowlist        = var.network.worker_egress_allowlist
  }
}

resource "terraform_data" "container_runtime" {
  input = {
    id                        = local.naming.runtime
    service_name              = var.container_service.name
    desired_count             = var.container_service.desired_count
    cpu                       = var.container_service.cpu
    memory                    = var.container_service.memory
    restricted_worker_egress  = var.container_service.restricted_worker_egress
    graceful_shutdown_seconds = var.container_service.graceful_shutdown_seconds
    image_contract            = "immutable-tag-plus-provenance"
  }
}

resource "terraform_data" "postgres" {
  input = {
    id                    = local.naming.postgres
    engine                = var.postgres.engine
    version               = var.postgres.version
    private               = var.postgres.private
    high_availability     = var.postgres.high_availability
    backup_retention_days = var.postgres.backup_retention_days
    deletion_protection   = var.postgres.deletion_protection
  }
}

resource "terraform_data" "redis" {
  input = {
    id             = local.naming.redis
    engine         = var.redis.engine
    version        = var.redis.version
    private        = var.redis.private
    tls_required   = var.redis.tls_required
    backup_enabled = var.redis.backup_enabled
  }
}

resource "terraform_data" "object_storage" {
  input = {
    id         = local.naming.object_storage
    kind       = var.object_storage.kind
    private    = var.object_storage.private
    encryption = var.object_storage.encryption
    versioning = var.object_storage.versioning
  }
}

resource "terraform_data" "secret_manager" {
  input = {
    id         = local.naming.secret_manager
    references = var.secret_references
    values     = "external-secret-manager-only"
  }
}

resource "terraform_data" "edge" {
  input = {
    id                       = local.naming.edge
    https_only               = var.edge.https_only
    tls_termination_at_edge  = var.network.tls_termination_at_edge
    certificate_reference    = var.edge.certificate_reference
    dns_managed_outside_repo = var.edge.dns_managed_outside_repo
  }
}

resource "terraform_data" "telemetry" {
  input = {
    id                      = local.naming.telemetry
    otlp_endpoint_reference = var.telemetry.otlp_endpoint_reference
    logs                    = var.telemetry.logs
    metrics                 = var.telemetry.metrics
    traces                  = var.telemetry.traces
  }
}

resource "terraform_data" "backups" {
  input = {
    id                         = local.naming.backups
    postgres_schedule          = var.backups.postgres_schedule
    object_storage_sync        = var.backups.object_storage_sync
    restore_rehearsal_required = var.backups.restore_rehearsal_required
  }
}
