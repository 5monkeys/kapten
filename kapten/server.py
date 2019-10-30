from starlette.applications import Starlette
from starlette.config import Config
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


@app.route("/webhook/dockerhub", methods=["POST"])
async def dockerhub_webhook(request):
    payload = await request.json()
    repositories = app.state.repositories

    try:
        image, callback_url = dockerhub.parse_webhook_payload(payload, repositories)
    except ValueError as e:
        logger.critical(e)
        return Response(status_code=404)

    # Callback and verify
    acked = dockerhub.callback(callback_url, "Valid webhook received")
    if not acked:
        logger.critical("Failed to call back to dockerhub", callback_url)
        return Response(status_code=400)

    try:
        # Update all services matching this image
        updated_services = app.state.client.update_services(image=image)
    except Exception as e:
        logger.error(e)
        return Response(status_code=500)

    if not updated_services:
        logger.error("No services updated by dockerhub webhook for image: %s", image)
        dockerhub.callback(callback_url, "Non-tracked image", state="failure")
        return Response(None, status_code=400)

    dockerhub.callback(
        callback_url,
        "Updated services: [{}]".format(", ".join((s.name for s in updated_services))),
    )

    return JSONResponse(
        [
            {"service": service.name, "image": service.image_with_digest}
            for service in updated_services
        ]
    )


def run(client: Kapten, host: str = "0.0.0.0", port: int = 8000):
    import uvicorn

    logger.info("Starting Kapten {} server ...".format(__version__))
    app.state.client = client
    app.state.repositories = client.list_repositories()

    uvicorn.run(app, host=host, port=port)
