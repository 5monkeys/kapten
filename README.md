# kapten

![](https://github.com/5monkeys/kapten/workflows/Test/badge.svg)

Updates a Docker Swarm service when a new image is available.

**Usage:**
```sh
$ kapten --help
usage: kapten [-h] -s SERVICES [--slack SLACK] [--check] [--force]
              [-v VERBOSITY]

Checks for new images and updates services if needed.

optional arguments:
  -h, --help            show this help message and exit
  -s SERVICES, --service SERVICES
                        Service to update
  --slack SLACK         Slack token to use for notification
  --check               Only check if service needs to be updated
  --force               Force service update
  -v VERBOSITY, --verbosity VERBOSITY
                        Level of verbosity
```

**Example:**
```sh
$ kapten --service app --slack abc/def/123
Updating service app to repo/app:latest@sha256:123456789
```
