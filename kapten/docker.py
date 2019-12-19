import base64
import copy
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Union

import httpx
from httpx.exceptions import ConnectTimeout
from httpx.models import QueryParamTypes

from .exceptions import KaptenAPIError, KaptenConnectionError

Filter = Optional[List[str]]


class Service(dict):
    @property
    def id(self) -> str:
        return self["ID"]

    @property
    def version(self) -> int:
        return self["Version"]["Index"]

    @property
    def stack(self) -> str:
        labels = self["Spec"]["TaskTemplate"]["ContainerSpec"]["Labels"]
        return labels.get("com.docker.stack.namespace")

    @property
    def name(self) -> str:
        return self["Spec"]["Name"]

    @property
    def short_name(self) -> str:
        name = self.name
        stack = self.stack
        if stack and name.startswith(stack + "_"):
            return name[len(stack) + 1 :]
        return self.name

    @property
    def image_with_digest(self) -> str:
        return self["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]

    @property
    def image(self) -> str:
        image = self.image_with_digest
        return image[: image.rindex("@")]

    @property
    def digest(self) -> str:
        digest = self.image_with_digest
        return digest[digest.rindex("@") + 1 :]

    @property
    def repository(self) -> str:
        repository = self.image
        return repository[: repository.index(":")]

    # @property
    # def tag(self):
    # image = self.image
    # return image[image.index(":") + 1 :]

    def clone(self, digest: str) -> "Service":
        clone = copy.deepcopy(self)
        task_template = clone["Spec"]["TaskTemplate"]
        task_template["ContainerSpec"]["Image"] = "{}@{}".format(self.image, digest)
        return clone


class DockerAPIClient:
    def __init__(self) -> None:
        base_url = os.environ.get("DOCKER_HOST", "unix://var/run/docker.sock")
        uds = None

        if base_url.startswith("unix://"):
            uds = base_url[6:]
            base_url = "http://localhost"
        else:
            base_url = base_url.replace("tcp://", "http://")

        self.config: Mapping[str, Any] = {"base_url": base_url, "uds": uds}

    def build_filters_param(self, **filters: Filter) -> Optional[Dict[str, str]]:
        params = {
            key: {value: True for value in values}
            for key, values in filters.items()
            if values is not None
        }
        return {"filters": json.dumps(params)} if params else None

    def get_auth_header(self) -> Dict[str, bytes]:
        username = os.environ.get("DOCKER_USERNAME")
        password = os.environ.get("DOCKER_PASSWORD")

        if not username or not password:
            return {}

        return {
            "X-Registry-Auth": base64.b64encode(
                json.dumps({"username": username, "password": password}).encode("utf-8")
            )
        }

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[QueryParamTypes] = None,
        data: Optional[Mapping] = None,
        authenticate: bool = False,
    ) -> Union[List, Dict]:
        async with httpx.Client(**self.config) as client:
            headers = self.get_auth_header() if authenticate else {}

            try:
                response = await client.request(
                    method, url, params=params or {}, json=data, headers=headers
                )
                result = response.json()
            except ConnectTimeout as e:
                raise KaptenConnectionError("Docker API Connection Error") from e
            except Exception as e:  # pragma: nocover
                raise KaptenAPIError("Docker API Error: {}".format(str(e))) from e

            if response.status_code >= 400:
                message = result["message"] if isinstance(result, dict) else "?"
                raise KaptenAPIError(f"Docker API Error: {message}")

            return result

    async def version(self) -> Dict:
        result = await self.request("GET", "/version")
        assert isinstance(result, dict), "Invalid response"
        return result

    # async def containers(self, **filters: Filter):
    # params = self.build_filters_param(**filters)
    # return await self.request("GET", "/containers/json", params=params)

    async def services(self, **filters: Filter) -> List[Service]:
        params = self.build_filters_param(**filters)
        result = await self.request("GET", "/services", params=params)
        assert isinstance(result, list), "Invalid response"
        return [Service(service) for service in result]

    async def distribution(self, image: str) -> Dict:
        url = f"/distribution/{image}/json"
        result = await self.request("GET", url, authenticate=True)
        assert isinstance(result, dict), "Invalid response"
        return result

    async def service_update(self, id_or_name: str, version: int, spec: Dict) -> Dict:
        url = "/services/{id}/update".format(id=id_or_name)

        params = {"version": version}
        result = await self.request(
            "POST", url, params=params, data=spec, authenticate=True
        )
        assert isinstance(result, dict), "Invalid response"
        return result
