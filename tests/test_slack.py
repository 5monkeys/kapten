from kapten import slack

from .testcases import KaptenTestCase


class SlackTestCase(KaptenTestCase):
    def test_notify(self):
        with self.mock_slack(token="token") as mocked:
            success = slack.notify(
                "token",
                "stack_service",
                "sha256:123456789",
                project="myapp",
                stack="stack",
                service_short_name="service",
                image_name="repo/image:tag",
                channel="kapten-deploy",
            )
            self.assertTrue(success)
            body = self.get_request_body(mocked)
            self.assertEqual(body["text"], "Deployment of *myapp* has started.")
            self.assertEqual(body["channel"], "kapten-deploy")

    def test_notify_missing_details(self):
        with self.mock_slack(token="token") as mocked:
            success = slack.notify("token", "stack_service", "sha256:123456789")
            self.assertTrue(success)
            body = self.get_request_body(mocked)
            self.assertEqual(body["text"], "Deployment of *stack_service* has started.")
            self.assertNotIn("channel", body)
