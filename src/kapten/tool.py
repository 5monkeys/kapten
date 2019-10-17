from datetime import datetime

from docker.api import APIClient

from . import slack

client = APIClient()


def get_latest_digest(image_name):
    data = client.inspect_distribution(image_name)
    digest = data["Descriptor"]["digest"]
    return digest


def update_service(spec, slack_token=None, verbosity=1, only_check=False, force=False):
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

    if verbosity >= 2:
        print("Stack:     {}".format(stack or "-"))
        print("Service:   {}".format(service_short_name))
        print("Image:     {}".format(image_name))
        print("  Current: {}".format(current_digest))
        print("  Latest:  {}".format(latest_digest))

    if force or latest_digest != current_digest:
        if only_check:
            print("Can update service {} to {}".format(service_name, latest_image))
            return

        if verbosity >= 1:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(
                "{} - Updating service {} to {}".format(now, service_name, latest_image)
            )

        # Update service to latest image
        task_template["ContainerSpec"]["Image"] = latest_image
        client.update_service(
            service_id,
            service_version,
            task_template=task_template,
            fetch_current_spec=True,
        )

        if slack_token:
            # Notify slack
            if verbosity >= 2:
                print("Notifying Slack...")

            slack.notify(
                slack_token,
                service_name,
                latest_digest,
                stack=stack,
                service_short_name=service_short_name,
                image_name=image_name,
            )


def update_services(
    service_names, slack_token=None, verbosity=1, only_check=False, force=False
):
    service_specs = client.services({"name": service_names})
    for service_spec in service_specs:
        try:
            update_service(
                service_spec,
                slack_token=slack_token,
                verbosity=verbosity,
                only_check=only_check,
                force=force,
            )
        except Exception as e:
            if verbosity > 0:
                print(
                    "Failed to update service {}: {}".format(
                        service_spec["Spec"]["Name"], e.message
                    )
                )
