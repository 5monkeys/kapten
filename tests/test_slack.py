from kapten import slack
from kapten.docker import Service

from .testcases import KaptenTestCase


class SlackTestCase(KaptenTestCase):
    def test_notify(self):
        services = [
            Service(
                self.build_service_response("foo_bar", "repo/foo:tag@sha256:123456789")
            ),
            Service(
                self.build_service_response("baz", "repo/foo:tag@sha256:123456789")
            ),
        ]
        with self.mock_slack(token="token") as mocked:
            success = slack.notify(
                "token", services, project="myapp", channel="kapten-deploy"
            )
            self.assertTrue(success)
            body = self.get_request_body(mocked)
            self.assertEqual(body["text"], "Deployment of *myapp* has started.")
            self.assertEqual(body["channel"], "kapten-deploy")

            fields = body["attachments"][0]["fields"]
            self.assertIsNotNone(fields[0]["value"])
            self.assertEqual(fields[1]["value"], "- (none)\n- foo")
            self.assertEqual(fields[2]["value"], "repo/foo:tag")
            self.assertEqual(fields[3]["value"], "sha256:123456789")
            self.assertEqual(fields[4]["value"], "- bar\n- baz")

    def test_notify_missing_details(self):
        service = Service(
            self.build_service_response("foo_bar", "repo/foo:tag@sha256:123456789")
        )
        with self.mock_slack(token="token") as mocked:
            success = slack.notify("token", [service])
            self.assertTrue(success)
            body = self.get_request_body(mocked)
            self.assertEqual(body["text"], "Deployment of *foo* has started.")
            self.assertNotIn("channel", body)

    def test_post_without_fields(self):
        with self.mock_slack(token="token") as mocked:
            success = slack.post("token", "Hello world")
            self.assertTrue(success)
            body = self.get_request_body(mocked)
            self.assertNotIn("attachments", body)
