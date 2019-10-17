import logging

from docker.api import APIClient

from . import slack

logger = logging.getLogger(__name__)
client = APIClient()


def get_latest_digest(image_name):
    data = client.inspect_distribution(image_name)
    digest = data["Descriptor"]["digest"]
    return digest


def update_service(spec, slack_token=None, only_check=False, force=False):
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
    latest_digest = get_latest_digest(image_name)
    latest_image = "{}@{}".format(image_name, latest_digest)

    logger.debug("Stack:     %s", stack or "-")
    logger.debug("Service:   %s", service_short_name)
    logger.debug("Image:     %s", image_name)
    logger.debug("  Current: %s", current_digest)
    logger.debug("  Latest:  %s", latest_digest)

    if force or latest_digest != current_digest:
        if only_check:
            logger.info("Can update service %s to %s", service_name, latest_image)
            return

        logger.info("Updating service %s to %s", service_name, latest_image)

        # Update service to latest image
        task_template["ContainerSpec"]["Image"] = latest_image
        client.update_service(
            service_id,
            service_version,
            task_template=task_template,
            fetch_current_spec=True,
        )

        # Notify slack
        if slack_token:
            slack.notify(
                slack_token,
                service_name,
                latest_digest,
                stack=stack,
                service_short_name=service_short_name,
                image_name=image_name,
            )


def update_services(service_names, slack_token=None, only_check=False, force=False):
    service_specs = client.services({"name": service_names})
    for service_spec in service_specs:
        try:
            update_service(
                service_spec,
                slack_token=slack_token,
                only_check=only_check,
                force=force,
            )
        except Exception as e:
            logger.critical(
                "Failed to update service %s: %s",
                service_spec["Spec"]["Name"],
                e.message,
            )
