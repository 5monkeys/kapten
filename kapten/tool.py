import copy
import os

from docker.api import APIClient
from docker.errors import APIError
from requests.exceptions import ConnectionError

from . import slack
from .exceptions import KaptenClientError, KaptenError
from .log import logger


class Service(dict):
    @property
    def id(self):
        return self["ID"]

    @property
    def version(self):
        return self["Version"]["Index"]

    @property
    def stack(self):
        labels = self["Spec"]["TaskTemplate"]["ContainerSpec"]["Labels"]
        return labels.get("com.docker.stack.namespace")

    @property
    def name(self):
        return self["Spec"]["Name"]

    @property
    def short_name(self):
        name = self.name
        stack = self.stack
        return name[len(stack) + 1 :] if name.startswith(stack + "_") else name

    @property
    def image_with_digest(self):
        return self["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]

    @property
    def image(self):
        image = self.image_with_digest
        return image[: image.rindex("@")]

    @property
    def digest(self):
        digest = self.image_with_digest
        return digest[digest.rindex("@") + 1 :]

    @property
    def repository(self):
        repository = self.image
        return repository[: repository.index(":")]

    # @property
    # def tag(self):
    # image = self.image
    # return image[image.index(":") + 1 :]

    def clone(self, digest):
        clone = copy.deepcopy(self)
        task_template = clone["Spec"]["TaskTemplate"]
        task_template["ContainerSpec"]["Image"] = "{}@{}".format(self.image, digest)
        return clone


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
        self.client = APIClient(base_url=os.environ.get("DOCKER_HOST"))

    def get_latest_digest(self, image):
        data = self.client.inspect_distribution(image)
        digest = data.get("Descriptor", {}).get("digest")
        if not digest:
            raise KaptenError("Failed to get latest digest for image: {}".format(image))
        return digest

    def list_services(self, image=None):
        try:
            service_specs = self.client.services({"name": self.service_names})
        except ConnectionError as e:
            raise KaptenClientError("Docker API Failure: {}".format(str(e)))
        except APIError as e:
            raise KaptenClientError("Docker API Error: {}".format(str(e)))

        # Sort specs in input order and filter out any non exact matches
        service_specs = sorted(
            filter(lambda s: s["Spec"]["Name"] in self.service_names, service_specs),
            key=lambda s: self.service_names.index(s["Spec"]["Name"]),
        )

        if len(service_specs) != len(self.service_names):
            raise KaptenError("Could not find all given services")

        services = [Service(spec) for spec in service_specs]

        # Filter by given image
        if image:
            services = list(filter(lambda s: s.image == image, services))

        return services

    def list_repositories(self):
        services = self.list_services()
        repositories = {service.repository for service in services}
        return sorted(repositories)

    def update_service(self, service, digest):
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
        self.client.update_service(
            service.id,
            service.version,
            task_template=new_service["Spec"]["TaskTemplate"],
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
                image=service.image,
            )

        return new_service

    def update_services(self, services=None, image=None):
        updated_services = []

        services = services or self.list_services(image=image)
        images = {
            image: self.get_latest_digest(image)
            for image in {service.image for service in services}
        }

        for service in services:
            digest = images[service.image]
            updated_service = self.update_service(service, digest=digest)
            if updated_service:
                updated_services.append(updated_service)

        return updated_services
