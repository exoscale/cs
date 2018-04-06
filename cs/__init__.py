import argparse
import json
import os
import sys
import time
from collections import defaultdict

try:
    from configparser import NoSectionError
except ImportError:  # python 2
    from ConfigParser import NoSectionError

try:
    import pygments
    from pygments.lexers import JsonLexer, YamlLexer
    from pygments.formatters import TerminalFormatter
except ImportError:
    pygments = None

try:
    import yaml
except ImportError:
    yaml = None

from .client import read_config, CloudStack, CloudStackException  # noqa


__all__ = ['read_config', 'CloudStack', 'CloudStackException']

if sys.version_info >= (3, 5):
    try:
        import aiohttp  # noqa
    except ImportError:
        pass
    else:
        from ._async import AIOCloudStack  # noqa
        __all__.append('AIOCloudStack')


def _format_json(data):
    """Pretty print a dict as a JSON, with colors if pygments is present."""
    output = json.dumps(data, indent=2, sort_keys=True)

    if pygments and sys.stdout.isatty():
        return pygments.highlight(output, JsonLexer(), TerminalFormatter())

    return output


def _format_yaml(data):
    """Pretty print a dict as a YAML, with colors if pygments is present."""
    output = yaml.safe_dump(data)

    if pygments and sys.stdout.isatty():
        return pygments.highlight(output, YamlLexer(), TerminalFormatter())

    return output


def main():
    parser = argparse.ArgumentParser(description='Cloustack client.')
    parser.add_argument('--region', metavar='REGION',
                        help='Cloudstack region in ~/.cloudstack.ini',
                        default=os.environ.get('CLOUDSTACK_REGION',
                                               'cloudstack'))
    parser.add_argument('--post', action='store_true', default=False,
                        help='use POST instead of GET')
    parser.add_argument('--async', action='store_true', default=False,
                        help='do not wait for async result')
    parser.add_argument('--quiet', '-q', action='store_true', default=False,
                        help='do not display additional status messages')
    parser.add_argument('--yaml', '-y', action='store_true', default=False,
                        help='convert output to YAML')
    parser.add_argument('command', metavar="COMMAND",
                        help='Cloudstack API command to execute')

    def parse_option(x):
        if '=' not in x:
            raise ValueError("{!r} is not a correctly formatted "
                             "option".format(x))
        return x.split('=', 1)

    parser.add_argument('arguments', metavar="OPTION=VALUE",
                        nargs='*', type=parse_option,
                        help='Cloudstack API argument')

    options = parser.parse_args()
    command = options.command
    kwargs = defaultdict(set)
    for arg in options.arguments:
        key, value = arg
        kwargs[key].add(value.strip(" \"'"))

    try:
        config = read_config(ini_group=options.region)
    except NoSectionError:
        raise SystemExit("Error: region '%s' not in config" % options.region)

    if options.post:
        config['method'] = 'post'
    cs = CloudStack(**config)
    ok = True
    try:
        response = getattr(cs, command)(**kwargs)
    except CloudStackException as e:
        response = e.args[1]
        if not options.quiet:
            sys.stderr.write("Cloudstack error: HTTP response "
                             "{0}\n".format(response.status_code))

        try:
            response = json.loads(response.text)
        except json.decoder.JSONDecodeError:
            sys.stderr.write(response.text)
            sys.stderr.write("\n")
            sys.exit(1)

    if 'Async' not in command and 'jobid' in response and not options.async:
        if not options.quiet:
            sys.stderr.write("Polling result... ^C to abort\n")
        while True:
            try:
                res = cs.queryAsyncJobResult(**response)
                if res['jobstatus'] != 0:
                    response = res
                    if res['jobresultcode'] != 0:
                        ok = False
                    break
                time.sleep(3)
            except KeyboardInterrupt:
                if not options.quiet:
                    sys.stderr.write("Result not ready yet.\n")
                break

    if options.yaml and yaml:
        sys.stdout.write(_format_yaml(response))
    else:
        sys.stdout.write(_format_json(response))
        sys.stdout.write('\n')
    sys.exit(int(not ok))
