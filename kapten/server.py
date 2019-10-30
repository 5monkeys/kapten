from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response

from . import __version__
from .log import logger
from .tool import Kapten

app = Starlette(debug=True)


@app.route("/version")
async def version(request):
    return JSONResponse({"kapten": __version__})


@app.route("/webhook/dockerhub", methods=["POST"])
async def dockerhub_webhook(request):
    payload = await request.json()

    # Validate payload schema
    if (
        "callback_url" not in payload
        or "repository" not in payload
        or "repo_name" not in payload["repository"]
        or "push_data" not in payload
        or "tag" not in payload["push_data"]
    ):
        logger.critical("Invalid dockerhub payload")
        return Response(status_code=404)

    # Validate callback url
    callback_url = payload["callback_url"]
    hooks = (
        "https://registry.hub.docker.com/u/{}/hook/".format(repository)
        for repository in app.state.repositories
    )
    if not callback_url or not any((callback_url.startswith(hook) for hook in hooks)):
        logger.critical("Invalid dockerhub callback url: %s", callback_url)
        return Response(status_code=404)

    # TODO: Ack callback url

    # Validate repository
    repository = payload["repository"]["repo_name"]
    if repository not in app.state.repositories:
        logger.critical("Invalid dockerhub repository: %s", repository)
        return Response(status_code=400)

    # Update all services matching this image
    tag = payload["push_data"]["tag"]
    image = "{}:{}".format(repository, tag)
    updated_services = app.state.client.update_services(image=image)

    if not updated_services:
        logger.error("No services updated by dockerhub webhook for image: %s", image)
        return Response(None, status_code=400)

    return JSONResponse(
        [
            {"service": service.name, "image": service.image_with_digest}
            for service in updated_services
        ]
    )


def run(client: Kapten, host: str = "0.0.0.0", port: int = 8000):
    import uvicorn

    app.state.client = client
    app.state.repositories = client.list_repositories()

    logger.info("Starting Kapten {} server ...".format(__version__))
    uvicorn.run(app, host=host, port=port)
