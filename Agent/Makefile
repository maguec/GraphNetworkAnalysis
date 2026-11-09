ifneq (,$(wildcard ../.env))
    include ../.env
    export
endif

default: help

##@ Utility
help:  ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

printenv: ## Print environment variables from ../.env
	@echo "Environment variables loaded from ../.env:"
	@echo "  GOOGLE_APPLICATION_CREDENTIALS=$(GOOGLE_APPLICATION_CREDENTIALS)"
	@echo "  GOOGLE_PROJECT=$(GOOGLE_PROJECT)"
	@echo "  GOOGLE_SPANNER_INSTANCE=$(GOOGLE_SPANNER_INSTANCE)"
	@echo "  GOOGLE_SPANNER_DATABASE=$(GOOGLE_SPANNER_DATABASE)"

gettoolbox: ## Download Linux MCP
	@echo "Downloading MCP for Linux"
	@rm -rf toolbox
	@wget https://storage.googleapis.com/genai-toolbox/v0.15.0/linux/amd64/toolbox
	@chmod +x toolbox

runtoolbox: printenv ## Run the toolbox command
	@set -a && . ../.env && set +a && ./toolbox --tools-file tools.yaml --log-level DEBUG

runadk: printenv ## Run the ADK web server
	@set -a && . ../.env && set +a && uv run adk web --host=0.0.0.0 --port 8089
