import asynctest

from kapten import github


class GitHubTestCase(asynctest.TestCase):
    def test_validate_signature(self):
        secret = "secret"
        request_body = "body"  # Bytes expected; this should raise
        signature = "sha1=abc123"
        self.assertFalse(github.validate_signature(secret, request_body, signature))
