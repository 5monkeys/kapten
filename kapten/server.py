import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse

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

    # TODO: Validate any service image is part of the callback url by:
    #
    #       Fetching repositories and set in app.state on server start
    #         - or -
    #       Don't require --service argument to allow all running services/images
    #
    #       Validate: https://registry.hub.docker.com/u/5monkeys/testhook/

    callback_url = payload["callback_url"]
    if not callback_url.startswith("https://registry.hub.docker.com/u/"):
        raise ValueError()

    # TODO: Ack callback url

    repository = payload["repository"]["repo_name"]
    tag = payload["push_data"]["tag"]
    image_name = "{}:{}".format(repository, tag)

    services = app.state.client.list_services(image_name)
    app.state.client.update_services(services)

    return JSONResponse(
        {"services": [service.name for service in services], "image": image_name}
    )


def run(client: Kapten, host: str, port: int):
    import uvicorn

    logger.info("Starting Kapten {} server ...".format(__version__))
    app.state.client = client
    uvicorn.run(app, host=host, port=port)
