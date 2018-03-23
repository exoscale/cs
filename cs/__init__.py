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
    from pygments.lexers import JsonLexer, XmlLexer
    from pygments.formatters import TerminalFormatter
except ImportError:
    pygments = None

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

if sys.version_info >= (3, 6):
    try:
        import lxml.etree
        from requests_xml import BaseParser
    except ImportError:
        pass


def _format_json(data):
    """Pretty print a dict as a JSON, with colors if pygments is present."""
    output = json.dumps(data, indent=2, sort_keys=True)

    if pygments and sys.stdout.isatty():
        return pygments.highlight(output, JsonLexer(), TerminalFormatter())

    return output


def _format_xml(data):
    """Pretty print the XML struct, with colors if pygments is present."""
    if not isinstance(data, BaseParser):
        output = []
        for elem in data:
            output.append(_format_xml(elem))
        return ''.join(output)

    output = lxml.etree.tostring(data.lxml, encoding=data.encoding,
                                 pretty_print=True)

    if pygments and sys.stdout.isatty():
        return pygments.highlight(output, XmlLexer(), TerminalFormatter())

    return output


def _parser():
    """Build the argument parser"""
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

    return parser


def mainx():
    """Just like main, but better"""
    parser = _parser()

    parser.add_argument('--xpath', metavar='XPATH',
                        help='XPath query into the result')

    parser.add_argument('--json', metavar='PARSER',
                        help='convert XML to JSON using given serializer, '
                             'e.g. yahoo')

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
    config['response'] = 'xml'

    cs = CloudStack(**config)
    ok = True
    try:
        response = getattr(cs, command)(**kwargs)
    except CloudStackException as e:
        response = e.args[1]
        if not options.quiet:
            sys.stderr.write("Cloudstack error: HTTP response "
                             "{0}\n".format(response.status_code))

        sys.stderr.write(response.text)
        sys.stderr.write("\n")
        sys.exit(1)

    if options.xpath:
        root = lxml.etree.Element("root")
        root.set("xpath", options.xpath)
        for child in response.xpath(options.xpath):
            root.append(child.element)
        response = BaseParser(element=root)

    if options.json:
        import xmljson
        serializer = getattr(xmljson, options.json)
        data = serializer.data(lxml.etree.fromstring(response.raw_xml))
        sys.stdout.write(_format_json(data))
        sys.stdout.write('\n')
    else:
        sys.stdout.write(_format_xml(response))
    sys.exit(not ok)


def main():
    parser = _parser()
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

    sys.stdout.write(_format_json(response))
    sys.stdout.write('\n')
    sys.exit(not ok)
