import logging
import socket

import requests

logger = logging.getLogger(__name__)


def post(token, text, fields=None, fallback=None):
    logger.debug("Notifying Slack...")
    payload = {"text": text}
    if fields:
        payload["attachments"] = [
            {"color": "#50ba32", "fallback": fallback or text, "fields": fields}
        ]
    response = requests.post(
        "https://hooks.slack.com/services/{}".format(token), json=payload
    )
    return response.text == "ok"


def notify(token, service_name, image_digest, **kwargs):
    project = kwargs.get("project", service_name)
    hostname = socket.gethostname()

    # Host:
    fields = [{"title": "Host", "value": hostname, "short": True}]

    # Stack:
    if "stack" in kwargs:
        fields.append({"title": "Stack", "value": kwargs["stack"], "short": True})

    # Image:
    if "image_name" in kwargs:
        fields.append({"title": "Image", "value": kwargs["image_name"], "short": True})

    # Service:
    fields.append(
        {
            "title": "Service",
            "value": kwargs.get("service_short_name", service_name),
            "short": True,
        }
    )

    # Digest:
    fields.append({"title": "Digest", "value": image_digest, "short": False})

    return post(
        token,
        "Deployment of *{}* has started.".format(project),
        fallback="Deploying {}, {}".format(service_name, image_digest),
        fields=fields,
    )
