import base64
import copy
import json
import os

import httpx
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


class DockerAPIClient:
    def __init__(self, *args, **kwargs):
        host = os.environ.get("DOCKER_HOST", "unix://var/run/docker.sock")
        base_url = None
        uds = None

        if host.startswith("unix://"):
            base_url = "http://localhost"
            uds = host[6:]
        elif host.startswith("tcp://"):
            base_url = host.replace("tcp://", "http://")

        self.config = {"base_url": base_url, "uds": uds}

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

    async def request(self, method, url, params=None, data=None, authenticate=False):
        async with httpx.Client(**self.config) as client:
            headers = self.get_auth_header() if authenticate else None

            try:
                response = await client.request(
                    method, url, params=params, json=data, headers=headers
                )
            except ConnectTimeout as e:
                raise KaptenConnectionError("Docker API Connection Error") from e
            except Exception as e:
                raise KaptenAPIError("Docker API Error: {}".format(str(e))) from e

            if response.status_code >= 400:
                error = response.json()
                raise KaptenAPIError("Docker API Error: {}".format(error["message"]))

            return response.json()

    async def version(self):
        return await self.request("GET", "/version")

    # async def containers(self, **filters):
    # params = self.build_filters_param(**filters)
    # return await self.request("GET", "/containers/json", params=params)

    async def services(self, **filters):
        params = self.build_filters_param(**filters)
        specs = await self.request("GET", "/services", params=params)
        return [Service(spec) for spec in specs]

    async def distribution(self, image):
        url = "/distribution/{name}/json".format(name=image)
        return await self.request("GET", url, authenticate=True)

    async def service_update(self, id_or_name, version, task_template):
        # TODO: Implement full post body
        url = "/services/{id}/update".format(id=id_or_name)

        params = {"version": version}
        data = {"TaskTemplate": task_template}

        return await self.request(
            "POST", url, params=params, data=data, authenticate=True
        )
