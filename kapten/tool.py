from docker.api import APIClient

from . import slack
from .exceptions import KaptenError
from .log import logger


# TODO: Extend dict
class Service:
    def __init__(self, spec):
        task_template = spec["Spec"]["TaskTemplate"]
        container_spec = task_template["ContainerSpec"]
        container_image = container_spec["Image"]
        image_name, _, current_digest = container_image.partition("@")
        repository, _, tag = image_name.partition(":")

        self.id = spec["ID"]
        self.version = spec["Version"]["Index"]
        self.stack = container_spec["Labels"].get("com.docker.stack.namespace", None)
        self.name = spec["Spec"]["Name"]
        self.short_name = (
            self.name[len(self.stack) + 1 :]
            if self.name.startswith(self.stack + "_")
            else self.name
        )
        self.repository = repository
        self.image_name = image_name  # TODO: Remove in favour of repository and tag?
        self.tag = tag
        self.digest = current_digest
        self.task_template = task_template

    def __repr__(self):
        return "<Service: {}>".format(self.name)


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
        self.client = APIClient()

    def get_latest_digest(self, image_name):
        data = self.client.inspect_distribution(image_name)
        digest = data.get("Descriptor", {}).get("digest")
        if not digest:
            raise KaptenError(
                "Failed to get latest digest for image: {}".format(image_name)
            )
        return digest

    def list_services(self, image_name=None):
        service_specs = self.client.services({"name": self.service_names})

        # Sort specs in input order and filter out any non exact matches
        service_specs = sorted(
            filter(lambda s: s["Spec"]["Name"] in self.service_names, service_specs),
            key=lambda s: self.service_names.index(s["Spec"]["Name"]),
        )

        if len(service_specs) != len(self.service_names):
            raise KaptenError("Could not find all given services")

        services = [Service(spec) for spec in service_specs]

        # Filter by given image
        if image_name:
            services = list(filter(lambda s: s.image_name == image_name, services))

        return services

    def update_service(self, service, digest):
        latest_image = "{}@{}".format(service.image_name, digest)

        logger.debug("Stack:     %s", service.stack or "-")
        logger.debug("Service:   %s", service.short_name)
        logger.debug("Image:     %s", service.image_name)
        logger.debug("  Current: %s", service.digest)
        logger.debug("  Latest:  %s", digest)

        if not self.force and digest == service.digest:
            return

        if self.only_check:
            logger.info("Can update service %s to %s", service.name, latest_image)
            return

        logger.info("Updating service %s to %s", service.name, latest_image)

        # Update service to latest image
        task_template = service.task_template
        task_template["ContainerSpec"]["Image"] = latest_image
        self.client.update_service(
            service.id,
            service.version,
            task_template=task_template,
            fetch_current_spec=True,
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
                image_name=service.image_name,
            )

        return latest_image

    def update_services(self, services=None, image_name=None):
        result = {}

        services = services or self.list_services(image_name=image_name)
        image_digests = {
            image_name: self.get_latest_digest(image_name)
            for image_name in {service.image_name for service in services}
        }

        for service in services:
            digest = image_digests[service.image_name]
            image = self.update_service(service, digest=digest)
            result[service.name] = image

        return result
