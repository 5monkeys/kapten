from unittest import mock

from kapten.dockerapi import DockerAPIClient

from .testcases import KaptenTestCase


class DockerAPITestCase(KaptenTestCase):
    def test_auth_config(self):
        services = [("foobar", "foo/bar:baz@sha256:1")]
        with self.mock_docker_api(services) as api:
            with mock.patch.dict(
                "os.environ", DOCKER_USERNAME="foo", DOCKER_PASSWORD="bar"
            ):
                client = DockerAPIClient()
                dist = client.inspect_distribution("foo/bar:baz")

                self.assertIsInstance(dist, dict)
                self.assertTrue(api.inspect_distribution.called)
                _, call_kwargs = api.inspect_distribution.call_args_list[0]
                self.assertDictEqual(
                    call_kwargs, {"auth_config": {"username": "foo", "password": "bar"}}
                )
