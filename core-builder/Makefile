DOCKER_IMAGE_NAME=seldonio/core-builder
DOCKER_IMAGE_VERSION=0.3
ARCH=ppc64el

build_docker_image:
	docker build --build-arg ARCH=${ARCH} --force-rm=true -t $(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_VERSION) .
push_to_registry:
	docker push $(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_VERSION)

