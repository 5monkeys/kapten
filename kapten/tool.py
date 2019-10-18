from docker.api import APIClient

from . import slack
from .log import logger


class Kapten(object):
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
        digest = data["Descriptor"]["digest"]
        return digest

    def update_service(self, spec):
        service_id = spec["ID"]
        service_version = spec["Version"]["Index"]
        service_name = spec["Spec"]["Name"]
        task_template = spec["Spec"]["TaskTemplate"]
        container_spec = task_template["ContainerSpec"]
        stack = container_spec["Labels"].get("com.docker.stack.namespace", None)
        service_short_name = (
            service_name[len(stack) + 1 :]
            if service_name.startswith(stack + "_")
            else service_name
        )
        container_image = container_spec["Image"]
        image_name, _, current_digest = container_image.partition("@")

        # Fetch latest image digest
        latest_digest = self.get_latest_digest(image_name)
        latest_image = "{}@{}".format(image_name, latest_digest)

        logger.debug("Stack:     %s", stack or "-")
        logger.debug("Service:   %s", service_short_name)
        logger.debug("Image:     %s", image_name)
        logger.debug("  Current: %s", current_digest)
        logger.debug("  Latest:  %s", latest_digest)

        if self.force or latest_digest != current_digest:
            if self.only_check:
                logger.info("Can update service %s to %s", service_name, latest_image)
                return

            logger.info("Updating service %s to %s", service_name, latest_image)

            # Update service to latest image
            task_template["ContainerSpec"]["Image"] = latest_image
            self.client.update_service(
                service_id,
                service_version,
                task_template=task_template,
                fetch_current_spec=True,
            )

            # Notify slack
            if self.slack_token:
                slack.notify(
                    self.slack_token,
                    service_name,
                    latest_digest,
                    channel=self.slack_channel,
                    project=self.project,
                    stack=stack,
                    service_short_name=service_short_name,
                    image_name=image_name,
                )

    def update_services(self):
        service_specs = self.client.services({"name": self.service_names})
        for service_spec in service_specs:
            try:
                self.update_service(service_spec)
            except Exception as e:
                logger.critical(
                    "Failed to update service %s: %s",
                    service_spec["Spec"]["Name"],
                    e.message,
                )
