import asyncio
import base64
import copy
import json
import os
import ssl
import typing
from functools import wraps
from urllib.parse import quote_plus, unquote_plus, urljoin

import httpx
from httpx.concurrency.asyncio import AsyncioBackend, TCPStream
from httpx.concurrency.base import BaseTCPStream
from httpx.config import TimeoutConfig
from httpx.exceptions import ConnectTimeout

from .exceptions import KaptenAPIError, KaptenConnectionError


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
        if stack and name.startswith(stack + "_"):
            return name[len(stack) + 1 :]
        return self.name

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


def catch_async_error(f):
    @wraps(f)
    async def async_wrapper(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except ConnectTimeout as e:
            raise KaptenConnectionError("Docker API Connection Error") from e
        except Exception as e:
            raise KaptenAPIError("Docker API Error") from e

    return async_wrapper


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


class DockerAPIClient:
    def __init__(self, *args, **kwargs):
        host = os.environ.get("DOCKER_HOST", "unix://var/run/docker.sock")

        if host.startswith("unix://"):
            path = quote_plus(host[6:])
            self.base_url = "http://{}".format(path)
            self.backend = AsyncioUnixSocketBackend()

        elif host.startswith("tcp://"):
            self.base_url = host.replace("tcp://", "http://")
            self.backend = None

    def get_url(self, path):
        return urljoin(self.base_url, path)

    def build_filters_param(self, **filters):
        params = {
            key: {value: True for value in values}
            for key, values in filters.items()
            if values is not None
        }
        return {"filters": json.dumps(params)} if params else ""

    def get_auth_header(self):
        username = os.environ.get("DOCKER_USERNAME")
        password = os.environ.get("DOCKER_PASSWORD")

        if not username or not password:
            return {}

        return {
            "X-Registry-Auth": base64.b64encode(
                json.dumps({"username": username, "password": password}).encode("utf-8")
            )
        }

    @catch_async_error
    async def version(self):
        async with httpx.AsyncClient(backend=self.backend) as client:
            url = self.get_url("/version")
            response = await client.get(url)
            return response.json()

    @catch_async_error
    async def containers(self, **filters):
        async with httpx.AsyncClient(backend=self.backend) as client:
            url = self.get_url("/containers/json")
            params = self.build_filters_param(**filters)
            response = await client.get(url, params=params)
            return response.json()

    @catch_async_error
    async def services(self, **filters):
        async with httpx.AsyncClient(backend=self.backend) as client:
            url = self.get_url("/services")
            params = self.build_filters_param(**filters)
            response = await client.get(url, params=params)

            if response.status_code == httpx.codes.INTERNAL_SERVER_ERROR:
                raise KaptenAPIError("Server Error")
            elif response.status_code == httpx.codes.SERVICE_UNAVAILABLE:
                raise KaptenAPIError("Docker node is not part of a swarm")

            specs = response.json()
            return [Service(spec) for spec in specs]

    @catch_async_error
    async def distribution(self, image):
        async with httpx.AsyncClient(backend=self.backend) as client:
            url = self.get_url("/distribution/{name}/json".format(name=image))
            headers = self.get_auth_header()
            response = await client.get(url, headers=headers)

            if response.status_code == httpx.codes.FORBIDDEN:
                raise KaptenAPIError("Unauthorized, authentication required")
            elif response.status_code == httpx.codes.UNAUTHORIZED:
                raise KaptenAPIError("Failed authentication or no image found")
            elif response.status_code == httpx.codes.INTERNAL_SERVER_ERROR:
                raise KaptenAPIError("Server Error")

            distribution = response.json()
            return distribution

    @catch_async_error
    async def service_update(
        self, id_or_name, version, task_template, fetch_current_spec=False
    ):
        # TODO: Implement full post body
        data = {"TaskTemplate": task_template}
        async with httpx.AsyncClient(backend=self.backend) as client:
            url = self.get_url("/services/{id}/update".format(id=id_or_name))
            headers = self.get_auth_header()
            response = await client.post(url, json=data, headers=headers)

            if response.status_code == httpx.codes.BAD_REQUEST:
                raise KaptenAPIError("Unauthorized, authentication required")
            elif response.status_code == httpx.codes.NOT_FOUND:
                raise KaptenAPIError("Unauthorized, authentication required")
            elif response.status_code == httpx.codes.INTERNAL_SERVER_ERROR:
                raise KaptenAPIError("Server Error")
            elif response.status_code == httpx.codes.SERVICE_UNAVAILABLE:
                raise KaptenAPIError("Docker node is not part of a swarm")

            result = response.json()
            return result
