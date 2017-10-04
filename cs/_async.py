import asyncio
import ssl

import aiohttp

from . import CloudStack, CloudStackException
from .client import transform


class AIOCloudStack(CloudStack):
    def __init__(self, job_timeout=None, poll_interval=2.0,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_timeout = job_timeout
        self.poll_interval = poll_interval

    def __getattr__(self, command):
        async def handler(**kwargs):
            return (await self._request(command, **kwargs))
        return handler

    async def _request(self, command, json=True, opcode_name='command',
                       fetch_list=False, fetch_result=True, **kwargs):
        kwarg, kwargs = self._prepare_request(command, json, opcode_name,
                                              fetch_list, **kwargs)

        ssl_context = None
        if self.cert:
            ssl_context = ssl.create_default_context(cafile=self.cert)
        connector = aiohttp.TCPConnector(verify_ssl=self.verify,
                                         ssl_context=ssl_context)

        async with aiohttp.ClientSession(read_timeout=self.timeout,
                                         conn_timeout=self.timeout,
                                         connector=connector) as session:
            handler = getattr(session, self.method)

            done = False
            final_data = []
            page = 1
            while not done:
                if fetch_list:
                    kwargs['page'] = page

                kwargs = transform(kwargs)
                kwargs.pop('signature', None)
                kwargs['signature'] = self._sign(kwargs)
                response = await handler(self.endpoint, **{kwarg: kwargs})

                ctype = response.headers['content-type'].split(';')[0]
                try:
                    data = await response.json(content_type=ctype)
                except ValueError as e:
                    msg = "Make sure endpoint URL {!r} is correct.".format(
                        self.endpoint)
                    raise CloudStackException(
                        "HTTP {0} response from CloudStack".format(
                            response.status),
                        response,
                        "{}. {}".format(e, msg))

                [key] = data.keys()
                data = data[key]
                if response.status != 200:
                    raise CloudStackException(
                        "HTTP {0} response from CloudStack".format(
                            response.status), response, data)
                if fetch_list:
                    try:
                        [key] = [k for k in data.keys() if k != 'count']
                    except ValueError:
                        done = True
                    else:
                        final_data.extend(data[key])
                        page += 1
                if fetch_result and 'jobid' in data:
                    try:
                        final_data = await asyncio.wait_for(
                            self._jobresult(data['jobid']),
                            self.job_timeout)
                    except asyncio.TimeoutError:
                        raise CloudStackException(
                            "Timeout waiting for async job result",
                            data['jobid'])
                    done = True
                else:
                    final_data = data
                    done = True
            return final_data

    async def _jobresult(self, jobid):
        failures = 0
        while True:
            try:
                j = await self.queryAsyncJobResult(jobid=jobid,
                                                   fetch_result=False)
                failures = 0
                if j['jobstatus'] != 0:
                    if j['jobresultcode'] != 0 or j['jobstatus'] != 1:
                        raise CloudStackException("Job failure", j)
                    if 'jobresult' not in j:
                        raise CloudStackException("Unkonwn job result", j)
                    return j['jobresult']

            except CloudStackException:
                raise

            except Exception:
                failures += 1
                if failures > 10:
                    raise

            await asyncio.sleep(self.poll_interval)
