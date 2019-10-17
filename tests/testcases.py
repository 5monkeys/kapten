import contextlib
import unittest

import responses


class KaptenTestCase(unittest.TestCase):
    @contextlib.contextmanager
    def mock_slack(self, response, token="A123/B456/C789"):
        slack_url = "https://hooks.slack.com/services/%s" % token
        with responses.RequestsMock() as mock_response:
            mock_response.add(
                responses.POST,
                slack_url,
                body=response,
                status=200,
                content_type="text/html",
            )
            yield
