.PHONY: help base image build web-build deploy deploy-dev up up-dev down down-dev logs logs-dev ps ps-dev restart clean

IMAGE_NAME ?= celery-crawl-hub
IMAGE_TAG ?= latest
BASE_IMAGE ?= $(IMAGE_NAME):base
APP_IMAGE ?= $(IMAGE_NAME):$(IMAGE_TAG)
COMPOSE := docker compose -f deploy/docker/docker-compose.yml
COMPOSE_DEV := docker compose --env-file .env.dev -f deploy/docker/docker-compose.yml

help:
	@echo "Targets:"
	@echo "  make deploy     ★ 一键部署: 构建后端镜像 + 前端 + 启动全栈"
	@echo "  make deploy-dev ★ 一键本地部署(使用 .env.dev)"
	@echo "  make base       Build base image (system + pip + Playwright). Run once."
	@echo "  make image      Build application image on top of base image."
	@echo "  make build      Shortcut: base + image."
	@echo "  make web-build  Build web frontend (React/Vite) into web/dist/."
	@echo "  make up         Start the full stack."
	@echo "  make up-dev     Start the full stack with .env.dev."
	@echo "  make down       Stop and remove containers."
	@echo "  make down-dev   Stop and remove .env.dev stack."
	@echo "  make logs       Tail logs of all services."
	@echo "  make logs-dev   Tail logs of .env.dev stack."
	@echo "  make ps         Show running services."
	@echo "  make ps-dev     Show running services for .env.dev stack."
	@echo "  make restart    Restart application services."
	@echo "  make clean      Remove built images."

base:
	docker build -f deploy/docker/BaseDockerfile -t $(BASE_IMAGE) .

image:
	docker build -f deploy/docker/Dockerfile -t $(APP_IMAGE) \
		--build-arg BASE_IMAGE=$(BASE_IMAGE) .

build: base image

web-build:
	@echo ">>> Building web frontend..."
	cd web && npm install --prefer-offline && npm run build

deploy: build web-build up
	@echo ">>> Stack is up. API: http://localhost:8000  Web: http://localhost:$${WEB_PORT:-3000}"

deploy-dev: build web-build up-dev
	@echo ">>> Dev stack is up (.env.dev). API: http://localhost:8000  Web: http://localhost:$${WEB_PORT:-3000}"

stop-local:
	@echo ">>> Killing local processes on ports 8000 / 5173..."
	-fuser -k 8000/tcp 2>/dev/null || true
	-fuser -k 5173/tcp 2>/dev/null || true

up:
	IMAGE=$(APP_IMAGE) $(COMPOSE) up -d

up-dev:
	IMAGE=$(APP_IMAGE) APP_ENV_FILE=.env.dev $(COMPOSE_DEV) up -d

down:
	$(COMPOSE) down

down-dev:
	APP_ENV_FILE=.env.dev $(COMPOSE_DEV) down

logs:
	$(COMPOSE) logs -f --tail=200

logs-dev:
	APP_ENV_FILE=.env.dev $(COMPOSE_DEV) logs -f --tail=200

ps:
	$(COMPOSE) ps

ps-dev:
	APP_ENV_FILE=.env.dev $(COMPOSE_DEV) ps

restart:
	$(COMPOSE) restart crawler-api crawler-celery-worker translate-schedule-worker crawler-celery-beat

clean:
	-docker image rm $(APP_IMAGE) $(BASE_IMAGE)
