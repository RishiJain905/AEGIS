variable "environment" {
  type = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be dev, staging, or production."
  }
}

variable "region" {
  type = string
}

variable "container_service" {
  type = object({
    name                      = string
    desired_count             = number
    cpu                       = string
    memory                    = string
    restricted_worker_egress  = bool
    graceful_shutdown_seconds = number
  })
}

variable "postgres" {
  type = object({
    engine                = string
    version               = string
    private               = bool
    high_availability     = bool
    backup_retention_days = number
    deletion_protection   = bool
  })
}

variable "redis" {
  type = object({
    engine         = string
    version        = string
    private        = bool
    tls_required   = bool
    backup_enabled = bool
  })
}

variable "object_storage" {
  type = object({
    kind       = string
    private    = bool
    encryption = string
    versioning = bool
  })
}

variable "secret_references" {
  type = set(string)
}

variable "network" {
  type = object({
    name                           = string
    private_data_subnets           = bool
    data_ingress_from_runtime_only = bool
    tls_termination_at_edge        = bool
    worker_egress_allowlist        = set(string)
  })
}

variable "edge" {
  type = object({
    https_only               = bool
    certificate_reference    = string
    dns_managed_outside_repo = bool
  })
}

variable "telemetry" {
  type = object({
    otlp_endpoint_reference = string
    logs                    = bool
    metrics                 = bool
    traces                  = bool
  })
}

variable "backups" {
  type = object({
    postgres_schedule          = string
    object_storage_sync        = string
    restore_rehearsal_required = bool
  })
}
