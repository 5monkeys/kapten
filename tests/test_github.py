import contextlib
import re

import httpx
import respx

from kapten import github

from .testcases import KaptenTestCase


class GitHubTestCase(KaptenTestCase):
    @contextlib.contextmanager
    def mock_github(
        self,
        repo_name="5monkeys/app",
        deploy_id=123,
        state="success",
        environment="development",
        description="Deployment finished successfully",
        with_api_exception=False,
    ):
        respx.post(
            re.compile(r"^https://api\.github\.com/repos/.*/deployments/.*/statuses$"),
            status_code=httpx.codes.UNAUTHORIZED
            if with_api_exception
            else httpx.codes.OK,
            content={},
            alias="github",
        )
        payload = {
            "url": f"https://api.github.com/repos/{repo_name}/deployments/{deploy_id}/statuses",
            "state": state,
            "environment": environment,
            "description": description,
        }
        yield payload

    def test_validate_signature(self):
        secret = "secret"
        request_body = "body"  # Bytes expected; this should raise
        signature = "sha1=abc123"
        self.assertFalse(github.validate_signature(secret, request_body, signature))

    async def test_callback(self):
        with self.mock_github() as callback_kwargs:
            result = await github.callback(**callback_kwargs)
            self.assertTrue(result)
            request_body = self.get_request_body("github")
            self.assertEqual(request_body["state"], "success")
            self.assertEqual(request_body["environment"], "development")
            self.assertIn("description", request_body)
            headers = self.get_request_headers("github")
            self.assertEqual(
                headers["Accept"], "application/vnd.github.flash-preview+json"
            )

    async def test_callback_invalid_state(self):
        with self.mock_github(state="unknown") as callback_kwargs:
            with self.assertRaises(ValueError):
                await github.callback(**callback_kwargs)

    async def test_callback_is_error(self):
        with self.mock_github(with_api_exception=True) as callback_kwargs:
            result = await github.callback(**callback_kwargs)
            self.assertFalse(result)
