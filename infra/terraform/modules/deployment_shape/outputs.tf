output "deployment_shape" {
  description = "Provider-neutral inventory consumed by a future approved provider module."
  value = {
    environment       = var.environment
    region            = var.region
    network_id        = local.naming.network
    runtime_id        = local.naming.runtime
    postgres_id       = local.naming.postgres
    redis_id          = local.naming.redis
    object_storage_id = local.naming.object_storage
    secret_manager_id = local.naming.secret_manager
    edge_id           = local.naming.edge
    telemetry_id      = local.naming.telemetry
    backups_id        = local.naming.backups
  }
}

output "secret_references" {
  description = "Names only; secret values are never represented in this module."
  value       = var.secret_references
}
