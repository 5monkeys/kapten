import requests


def post(token, text, fields=None, fallback=None):
    payload = {"text": text}
    if fields:
        payload["attachments"] = [
            {"color": "#50ba32", "fallback": fallback or text, "fields": fields}
        ]
    return requests.post(
        "https://hooks.slack.com/services/{}".format(token), json=payload
    )


def notify(token, service_name, image_digest, **kwargs):
    fields = []
    if "stack" in kwargs:
        fields.append({"title": "Stack", "value": kwargs["stack"], "short": True})

    fields.append(
        {
            "title": "Service",
            "value": kwargs.get("service_short_name", service_name),
            "short": True,
        }
    )

    if "image_name" in kwargs:
        fields.append({"title": "Image", "value": kwargs["image_name"], "short": False})

    fields.append({"title": "Digest", "value": image_digest, "short": False})

    return post(
        token,
        "Deployment of *{}* has started.".format(service_name),
        fallback="Deploying {}, {}".format(service_name, image_digest),
        fields=fields,
    )
