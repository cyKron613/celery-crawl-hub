.PHONY: help base image build up down logs ps restart clean

IMAGE_NAME ?= celery-crawl-hub
IMAGE_TAG ?= latest
BASE_IMAGE ?= $(IMAGE_NAME):base
APP_IMAGE ?= $(IMAGE_NAME):$(IMAGE_TAG)
COMPOSE := docker compose -f deploy/docker/docker-compose.yml

help:
	@echo "Targets:"
	@echo "  make base       Build base image (system + pip + Playwright). Run once."
	@echo "  make image      Build application image on top of base image."
	@echo "  make build      Shortcut: base + image."
	@echo "  make up         Start the full stack (postgres + redis + api + workers + beat)."
	@echo "  make down       Stop and remove containers."
	@echo "  make logs       Tail logs of all services."
	@echo "  make ps         Show running services."
	@echo "  make restart    Restart application services."
	@echo "  make clean      Remove built images."

base:
	docker build -f deploy/docker/BaseDockerfile -t $(BASE_IMAGE) .

image:
	docker build -f deploy/docker/Dockerfile -t $(APP_IMAGE) \
		--build-arg BASE_IMAGE=$(BASE_IMAGE) .

build: base image

up:
	IMAGE=$(APP_IMAGE) $(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

restart:
	$(COMPOSE) restart crawler-api crawler-celery-worker translate-schedule-worker crawler-celery-beat

clean:
	-docker image rm $(APP_IMAGE) $(BASE_IMAGE)
