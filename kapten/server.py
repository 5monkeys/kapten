from starlette.applications import Starlette
from starlette.config import Config
from starlette.datastructures import Secret
from starlette.responses import JSONResponse, Response

from . import __version__, dockerhub
from .log import logger
from .tool import Kapten

config = Config()
app = Starlette()
app.debug = config("KAPTEN_DEBUG", cast=bool, default=False)


@app.route("/version")
async def version(request):
    return JSONResponse({"kapten": __version__})


@app.route("/webhook/dockerhub/{token}", methods=["POST"])
async def dockerhub_webhook(request):
    logger.info("Received dockerhub webhook from: %s", request.client.host)

    # Validate token
    if request.path_params["token"] != str(app.state.token):
        logger.critical("Invalid dockerhub token")
        return Response(status_code=404)

    payload = await request.json()
    repositories = app.state.repositories

    # Parse payload
    try:
        image, callback_url = dockerhub.parse_webhook_payload(payload, repositories)
    except ValueError as e:
        logger.critical(e)
        return Response(status_code=404)

    # Call back to dockerhub to verify legit webhook
    acked = dockerhub.callback(callback_url, "Valid webhook received")
    if not acked:
        logger.critical("Failed to call back to dockerhub on url: %s", callback_url)
        return Response(status_code=400)

    # Update all services matching this image
    try:
        updated_services = app.state.client.update_services(image=image)
    except Exception as e:
        logger.error(e)
        return Response(status_code=500)

    if not updated_services:
        logger.debug("No service(s) updated for image: %s", image)

    return JSONResponse(
        [
            {"service": service.name, "image": service.image_with_digest}
            for service in updated_services
        ]
    )


def run(client: Kapten, token: str, host: str = "0.0.0.0", port: int = 8800):
    import uvicorn

    logger.info("Starting Kapten {} server ...".format(__version__))
    app.state.client = client
    app.state.token = Secret(token)
    app.state.repositories = client.list_repositories()

    uvicorn.run(app, host=host, port=port, proxy_headers=True)
