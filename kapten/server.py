from starlette.applications import Starlette
from starlette.config import Config
from starlette.datastructures import Secret
from starlette.responses import JSONResponse, Response

from . import __version__, dockerhub
from .exceptions import KaptenAPIError
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
    acked = await dockerhub.callback(callback_url, "Valid webhook received")
    if not acked:
        logger.critical("Failed to call back to dockerhub on url: %s", callback_url)
        return Response(status_code=400)

    # Update all services matching this image
    try:
        updated_services = await app.state.client.update_services(image=image)
    except KaptenAPIError as e:
        logger.warning(e)
        return Response(status_code=503)
    except Exception as e:  # pragma: nocover
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


@app.on_event("startup")
async def setup() -> None:
    app.state.repositories = await app.state.client.list_repositories()


def run(client: Kapten, token: str, host: str = "0.0.0.0", port: int = 8800) -> None:
    import uvicorn

    logger.info(f"Starting Kapten {__version__} server ...")
    app.state.client = client
    app.state.token = Secret(token)

    uvicorn.run(app, host=host, port=port, proxy_headers=True)
