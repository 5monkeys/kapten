from . import slack
from .docker import DockerAPIClient
from .exceptions import KaptenError
from .log import logger


class Kapten:
    def __init__(
        self,
        service_names,
        project=None,
        slack_token=None,
        slack_channel=None,
        only_check=False,
        force=False,
    ):
        self.service_names = service_names
        self.project = project
        self.slack_token = slack_token
        self.slack_channel = slack_channel
        self.only_check = only_check
        self.force = force
        self.docker = DockerAPIClient()

    async def healthcheck(self):
        logger.info("Verifying connectivity and access to Docker API ...")

        # Ensure docker api version >= 1.24
        version = await self.docker.version()
        api_version = tuple(map(int, version["ApiVersion"].split(".")))
        if api_version < (1, 24):
            raise KaptenError(
                "Docker API version not supported, {} < 1.24".format(
                    version["ApiVersion"]
                )
            )

        # Verify tracked services
        services = await self.list_services()

        # Verify access to one of the services repository access
        await self.get_latest_digest(services[0].image)

        nof_services = len(services)
        logger.info(
            "Tracking {} service{}", nof_services, "s" if nof_services > 1 else ""
        )

        return nof_services

    async def get_latest_digest(self, image):
        # Get latest repository image info
        data = await self.docker.distribution(image)

        # Locate latest digest
        digest = data["Descriptor"]["digest"]

        return digest

    async def list_services(self, image=None):
        # List services
        services = await self.docker.services(name=self.service_names)

        # Sort in input order and filter out any non exact matches
        services = sorted(
            filter(lambda s: s.name in self.service_names, services),
            key=lambda s: self.service_names.index(s.name),
        )

        # Assert we got the services we asked for
        if len(services) != len(self.service_names):
            raise KaptenError("Could not find all tracked services")

        # Filter by given image
        if image:
            services = list(filter(lambda s: s.image == image, services))

        return services

    async def list_repositories(self):
        services = await self.list_services()
        repositories = {service.repository for service in services}
        return sorted(repositories)

    async def update_service(self, service, digest):
        logger.debug("Stack:     %s", service.stack or "-")
        logger.debug("Service:   %s", service.short_name)
        logger.debug("Image:     %s", service.image)
        logger.debug("  Current: %s", service.digest)
        logger.debug("  Latest:  %s", digest)

        if not self.force and digest == service.digest:
            return

        # Clone service spec with new image digest
        new_service = service.clone(digest)

        if self.only_check:
            logger.info(
                "Can update service %s to %s",
                service.name,
                new_service.image_with_digest,
            )
            return new_service

        logger.info(
            "Updating service %s to %s", service.name, new_service.image_with_digest
        )

        # Update service to latest image digest
        await self.docker.service_update(
            service.id,
            service.version,
            task_template=new_service["Spec"]["TaskTemplate"],
        )

        # Notify slack
        if self.slack_token:
            slack.notify(
                self.slack_token,
                service.name,
                digest,
                channel=self.slack_channel,
                project=self.project,
                stack=service.stack,
                service_short_name=service.short_name,
                image=service.image,
            )

        return new_service

    async def update_services(self, image=None):
        updated_services = []

        # TODO: Run requests in parallel
        services = await self.list_services(image=image)
        images = {
            image: await self.get_latest_digest(image)
            for image in {service.image for service in services}
        }

        # TODO: Run requests in parallel
        for service in services:
            digest = images[service.image]
            updated_service = await self.update_service(service, digest=digest)
            if updated_service:
                updated_services.append(updated_service)

        return updated_services
