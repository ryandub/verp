import logging
import skew
import skew.awsclient
import sys

from concurrent import futures
from simpl import config

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


OPTIONS = [
    config.Option("--account",
                  help="AWS Account ID",
                  env="AWS_ACCOUNT_ID"),
    config.Option("--aws-access-key-id",
                  help="AWS Access Key ID",
                  required=False,
                  env="AWS_ACCESS_KEY_ID"),
    config.Option("--aws-secret-access-key",
                  help="AWS Secret Access Key",
                  required=False,
                  env="AWS_SECRET_ACCESS_KEY"),
    config.Option("--aws-session-token",
                  help="AWS Session Token",
                  required=False,
                  env="AWS_SESSION_TOKEN"),
    config.Option("--no-async",
                  dest="async",
                  help="Discover services serially",
                  action="store_false"),
]


class Verp(object):

    def __init__(self, account, creds, async):
        self.async = async
        self.account = account
        self.creds = creds
        self.resources = {}

        skew.config._config = {
            'accounts': {
                account: {
                    'credentials': creds
                }
            }
        }

    def _discover_service(self, service):
        """
        Perform a skew scan of the passed service.
        """
        resources = []
        arn = skew.scan('arn:aws:{0}:*:*:*/*'.format(service))
        for item in arn:
            try:
                resources.append(item)
            except Exception as exc:
                print("Error iterating resource item: %s" % str(exc))
                pass

        return resources

    def discover_resources(self):
        """
        Use skew to discover all active resources on supported services.
        """
        results = {}
        async_reqs = {}
        totals = {}
        services = [
            s for s in skew.resources.all_services('aws') if s != 'elb'
        ]

        if self.async:
            with futures.ThreadPoolExecutor(max_workers=15) as pool:
                for service in services:
                    fut = pool.submit(
                        self._discover_service,
                        service,
                    )
                    async_reqs[fut] = service
                for result in futures.as_completed(async_reqs):
                    name = async_reqs[result]
                    results[name] = result.result()
        else:
            for service in services:
                result = self._discover_service(service)
                results[service] = result
        for k, v in results.items():
            if v:
                print(('%s: The %s service has the following'
                       ' active arns:\n    %s') % (
                      self.account,
                      k,
                      '\n    '.join([str(i) for i in list(v)])))
                totals[k] = len(list(v))

        print('\nTotals:')
        for k, v in totals.items():
            print("    %s: %d" % (k, v))


def main():
    """Produce a Verp."""
    conf = config.Config(options=OPTIONS)
    conf.parse()

    creds = {
        'aws_access_key_id': conf.aws_access_key_id,
        'aws_secret_access_key': conf.aws_secret_access_key,
        'aws_session_token': conf.aws_session_token,
    }
    verp = Verp(conf.account, creds, conf.async)
    verp.discover_resources()

if __name__ == "__main__":
    main()
