from kapten import slack

from .testcases import KaptenTestCase


class SlackTestCase(KaptenTestCase):
    def test_notify(self):
        with self.mock_slack(token="token"):
            success = slack.notify(
                "token",
                "stack_service",
                "sha256:123456789",
                stack="stack",
                service_short_name="service",
                image_name="repo/image:tag",
            )
            self.assertTrue(success)
