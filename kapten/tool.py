import asyncio
from typing import Callable, Dict, List, Optional

from . import slack
from .docker import DockerAPIClient, Service
from .exceptions import KaptenAPIError, KaptenError
from .log import logger


class Kapten:
    def __init__(
        self,
        service_names: List[str],
        project: Optional[str] = None,
        slack_token: Optional[str] = None,
        slack_channel: Optional[str] = None,
        only_check: bool = False,
        force: bool = False,
    ) -> None:
        self.service_names = service_names
        self.project = project
        self.slack_token = slack_token
        self.slack_channel = slack_channel
        self.only_check = only_check
        self.force = force
        self.docker = DockerAPIClient()
        self.subscriptions = []

    async def healthcheck(self) -> int:
        logger.info("Verifying connectivity and access to Docker API ...")

        # Ensure docker api version >= 1.39
        version = await self.docker.version()
        api_version = tuple(map(int, version["ApiVersion"].split(".")))
        if api_version < (1, 39):
            raise KaptenError(
                "Docker API version not supported, {v} < 1.39".format(
                    v=version["ApiVersion"]
                )
            )

        # Verify tracked services
        services = await self.list_services()

        # Verify access to all service repositories
        images = list({service.image for service in services})
        await self.get_latest_digests(images)

        nof_services = len(services)
        logger.info(
            "Tracking %s service%s", nof_services, "s" if nof_services > 1 else ""
        )

        return nof_services

    async def get_latest_digest(self, image: str) -> str:
        # Get latest repository image info
        data = await self.docker.distribution(image)

        # Locate latest digest
        digest = data["Descriptor"]["digest"]

        return digest

    async def get_latest_digests(self, images: List[str]) -> Dict[str, str]:
        digests = await asyncio.gather(
            *(self.get_latest_digest(image) for image in images), return_exceptions=True
        )
        image_digests = dict(zip(images, digests))

        # Handle failing digists
        failed_images: Dict[str, Exception] = {
            image: digest
            for image, digest in image_digests.items()
            if isinstance(digest, Exception)
        }
        if failed_images:
            raise KaptenError(
                f"Failed fetching digests for images: {failed_images.keys()!r}"
            ) from next(iter(failed_images.values()))

        return image_digests

    async def list_services(self, image: Optional[str] = None) -> List[Service]:
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
            # TODO: Filter with regex match instead of exact match
            services = list(filter(lambda s: s.image == image, services))

        return services

    async def list_repositories(self) -> List[str]:
        services = await self.list_services()
        repositories = {service.repository for service in services}
        return sorted(repositories)

    async def update_service(self, service: Service, digest: str) -> Optional[Service]:
        logger.debug("Stack:     %s", service.stack or "-")
        logger.debug("Service:   %s", service.short_name)
        logger.debug("Image:     %s", service.image)
        logger.debug("  Current: %s", service.digest)
        logger.debug("  Latest:  %s", digest)

        if not self.force and digest == service.digest:
            return None

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
            service.id, service.version, spec=new_service["Spec"]
        )

        return new_service

    async def update_services(self, image: str = "") -> List[Service]:
        updated_services = []

        # List services
        image, _, digest = image.partition("@")
        services = await self.list_services(image=image)

        if not digest:
            # Fetch latest digests for service's images
            images = list({service.image for service in services})
            digests = await self.get_latest_digests(images)
        else:
            digests = {service.image: digest for service in services}

        # Deploy services
        results = await asyncio.gather(
            *(
                self.update_service(service, digest=digests[service.image])
                for service in services
            ),
            return_exceptions=True,
        )
        service_names = [service.name for service in services]
        service_results = dict(zip(service_names, results))

        # Handle failing services
        failed_services: Dict[str, Exception] = {
            key: value
            for key, value in service_results.items()
            if isinstance(value, Exception)
        }
        if failed_services:
            raise KaptenAPIError(
                f"Failed updating services: {failed_services.keys()!r}"
            ) from next(iter(failed_services.values()))

        # Filter updated services
        updated_services = [
            service
            for service in service_results.values()
            if isinstance(service, Service)
        ]

        # Notify slack
        # TODO: Notify failed services to slack?
        if self.slack_token:
            await slack.notify(
                self.slack_token,
                updated_services,
                project=self.project,
                channel=self.slack_channel,
            )

        return updated_services

    def listen(self):
        asyncio.ensure_future(self.handle_events())

    async def handle_events(self):
        """
        {
            "Type": "service",
            "Action": "update",
            "Actor": {
                "ID": "udb7rusq91ob0uhi337v2f2ro",
                "Attributes": {
                    "name": "toborrow-kapten-dev_kapten",
                    "updatestate.new": "completed",
                    "updatestate.old": "updating",
                },
            },
            "scope": "swarm",
            "time": 1576850575,
            "timeNano": 1576850575170197441,
        }
        """
        async for event in self.docker.events(type=["service"], event=["update"]):
            try:
                done_subscription_index = None
                for i, (subscription, _) in enumerate(self.subscriptions):
                    for rule in subscription:
                        matched = rule.match(event)
                        if matched:
                            break
                    if all(rule.completed for rule in subscription):
                        done_subscription_index = i
                        break

                if done_subscription_index is not None:
                    logger.info("All Services Deploymed!")
                    _, callback = self.subscriptions.pop(done_subscription_index)
                    callback()

            except Exception as e:
                logger.error("Failed to log event :-( %r", e, exc_info=True)

    def subscribe(self, services: List[Service], callback: Callable):
        rules = [
            ServiceUpdateRule(service=service.name, image=service.image_with_digest)
            for service in services
        ]
        self.subscriptions.append((rules, callback))


class ServiceUpdateRule:
    def __init__(self, service, image):
        self.service = service
        self.image = image
        self.checks = set()
        self.completed = False

    def match(self, event):
        attributes = event["Actor"]["Attributes"]
        service_name = attributes["name"]

        if service_name != self.name:
            return False

        image = attributes.get("image.new")
        state = attributes.get("updatestate.new")

        if image == self.image:
            self.checks.add("image")
            logger.info(f"Got image for service: {self.service}")
        elif state and "image" in self.checks:
            self.checks.add("state")
            self.deployed = True
            logger.info(f"Service deployed: {self.service}")

        return True
