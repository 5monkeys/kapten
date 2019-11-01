import asyncio
import copy
import os
import ssl
import typing
from urllib.parse import quote_plus, unquote_plus, urljoin

import httpx
from docker.api import APIClient
from docker.errors import APIError
from httpx.concurrency.asyncio import AsyncioBackend, TCPStream
from httpx.concurrency.base import BaseTCPStream
from httpx.config import TimeoutConfig
from httpx.exceptions import ConnectTimeout
from requests.exceptions import ConnectionError

from .exceptions import KaptenAPIError


class Service(dict):
    @property
    def id(self):
        return self["ID"]

    @property
    def version(self):
        return self["Version"]["Index"]

    @property
    def stack(self):
        labels = self["Spec"]["TaskTemplate"]["ContainerSpec"]["Labels"]
        return labels.get("com.docker.stack.namespace")

    @property
    def name(self):
        return self["Spec"]["Name"]

    @property
    def short_name(self):
        name = self.name
        stack = self.stack
        return name[len(stack) + 1 :] if name.startswith(stack + "_") else name

    @property
    def image_with_digest(self):
        return self["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]

    @property
    def image(self):
        image = self.image_with_digest
        return image[: image.rindex("@")]

    @property
    def digest(self):
        digest = self.image_with_digest
        return digest[digest.rindex("@") + 1 :]

    @property
    def repository(self):
        repository = self.image
        return repository[: repository.index(":")]

    # @property
    # def tag(self):
    # image = self.image
    # return image[image.index(":") + 1 :]

    def clone(self, digest):
        clone = copy.deepcopy(self)
        task_template = clone["Spec"]["TaskTemplate"]
        task_template["ContainerSpec"]["Image"] = "{}@{}".format(self.image, digest)
        return clone


def error_handler(f):
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ConnectionError as e:
            raise KaptenAPIError("Docker API Failure: {}".format(str(e))) from e
        except APIError as e:
            raise KaptenAPIError("Docker API Error: {}".format(str(e))) from e

    return wrapper


class AsyncioUnixSocketBackend(AsyncioBackend):
    async def open_tcp_stream(
        self,
        hostname: str,
        port: int,
        ssl_context: typing.Optional[ssl.SSLContext],
        timeout: TimeoutConfig,
    ) -> BaseTCPStream:
        try:
            path = unquote_plus(hostname)
            stream_reader, stream_writer = await asyncio.wait_for(  # type: ignore
                asyncio.open_unix_connection(path, ssl=ssl_context),
                timeout.connect_timeout,
            )
        except asyncio.TimeoutError:
            raise ConnectTimeout()

        return TCPStream(
            stream_reader=stream_reader, stream_writer=stream_writer, timeout=timeout
        )


class DockerAPIClient(APIClient):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("base_url", os.environ.get("DOCKER_HOST"))
        super().__init__(*args, **kwargs)

        host = os.environ.get("DOCKER_HOST", "unix://var/run/docker.sock")

        if host.startswith("unix://"):
            path = quote_plus(host[6:])
            self.base_url = "http://{}".format(path)
            self.backend = AsyncioUnixSocketBackend()

        elif host.startswith("tcp://"):
            self.base_url = host.replace("tcp://", "http://")
            self.backend = None

    def get_url(self, path):
        return urljoin(self.base_url, "/version")

    async def version(self):
        async with httpx.AsyncClient(backend=self.backend) as client:
            url = self.get_url("/version")
            response = await client.get(url)
            return response.json()

    @error_handler
    def services(self, names=None):
        specs = super().services({"name": names or []})
        return [Service(spec) for spec in specs]

    @error_handler
    def inspect_distribution(self, image):
        # Override auth config if environment variables present
        auth_config = None
        username = os.environ.get("DOCKER_USERNAME")
        password = os.environ.get("DOCKER_PASSWORD")
        if username and password:
            auth_config = {"username": username, "password": password}

        return super().inspect_distribution(image, auth_config=auth_config)

    @error_handler
    def update_service(self, *args, **kwargs):
        kwargs.setdefault("fetch_current_spec", True)
        return super().update_service(*args, **kwargs)
