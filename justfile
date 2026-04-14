COMPOSE_DIR := "infra/compose"
COMPOSE_BASE := COMPOSE_DIR + "/compose.yml"
COMPOSE_DEV := COMPOSE_DIR + "/compose.development.yml"
COMPOSE_PROD := COMPOSE_DIR + "/compose.prod.yml"

# Starts the local development environment
up:
    podman compose -f {{COMPOSE_BASE}} -f {{COMPOSE_DEV}} up -d

# Stops the local development environment
down:
    podman compose -f {{COMPOSE_BASE}} -f {{COMPOSE_DEV}} down

# Shows logs for local containers
logs +SERVICES="":
    podman compose -f {{COMPOSE_BASE}} -f {{COMPOSE_DEV}} logs -f {{SERVICES}}

# Run compose workloads for local development
compose +ARGS="":
    podman compose -f {{COMPOSE_BASE}} -f {{COMPOSE_DEV}} {{ARGS}}
