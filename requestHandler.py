import pickle

import aiohttp
import json
import time
import asyncio

import requests
import zmq
import zmq.asyncio

from models import Proxy
from contextlib import asynccontextmanager
from loggingUtils import loggingConfig
from config.cfg import config


def getProxiesList(startCutOff=0, endCutOff=-1):
    result = []
    count = 1000000000  # inf
    page = 1

    with open('data/webShareKey.txt', 'r') as file:
        key = file.read()

    session = requests.session()
    while count > len(result):
        url = f'https://proxy.webshare.io/api/proxy/list/?page={page}'

        for i in range(3):
            try:
                response = session.get(url, timeout=15, headers={"Authorization": f"Token {key}"}).json()

                if 'results' not in response:
                    raise Exception(json.dumps(response))

                count = response['count']
                response = response['results']
                break
            except Exception as e:
                print(f'could not get proxiesList - {e}')

                if i == 2:
                    return None
            time.sleep(20)

        page += 1

        for proxy in response:
            url = f"http://{proxy['username']}:{proxy['password']}@{proxy['proxy_address']}:{proxy['ports']['http']}"
            result.append(url)

    if startCutOff > len(result):
        return []

    if endCutOff == -1 or endCutOff > len(result):
        endCutOff = len(result)

    return result[startCutOff:endCutOff]
class TooManyRequests(Exception):
    pass

class RequestHandler(loggingConfig.AbstractLoggingClass):
    address = "tcp://127.0.0.1:1337"
    steam = 'steamcommunity.com'
    cs_money = 'cs.money'
    csgo_float = 'api.csgofloat.com'
    _open_sockets = 0

    cfg = config().this()

    def __init__(self):
        self._proxies: set[Proxy] = set([Proxy(url) for url in getProxiesList()])
        self._cache = {}
        all_hosts = list(self.cfg['delays'].keys()) + self.cfg["host_without_proxy"]
        self._requests_made = {host: 0 for host in all_hosts}
        self._requests_successful = {host: 0 for host in all_hosts}
        self._429_count = {host: 0 for host in all_hosts}

    async def start(self):
        tasks = [asyncio.ensure_future(self._run_server()), asyncio.ensure_future(self._log_stats())]
        await asyncio.gather(*tasks)

    @asynccontextmanager
    async def _get_proxy(self, hostname: str) -> Proxy:
        def key_function(x: Proxy):
            if hostname not in x.last_requests:
                x.last_requests[hostname] = 0

            return x.last_requests[hostname]

        while not self._proxies or time.time() - sorted(self._proxies, key=key_function)[0].last_requests[hostname] \
                < self.cfg['delays'][hostname]:
            await asyncio.sleep(0.01)

        proxy: Proxy = sorted(self._proxies, key=key_function)[0]
        self._proxies.remove(proxy)

        try:
            yield proxy
        finally:
            self._proxies.add(proxy)

    async def _log_stats(self):
        while True:
            await asyncio.sleep(60)

            for hostname, number_of_requests in self._requests_made.items():
                if number_of_requests > 0:
                    rate = self._requests_successful[hostname] / number_of_requests

                    if hostname == self.steam and number_of_requests > 1000 and rate < 0.4:
                        self.logger.critical('low success rate')

                    requests_per_minute = number_of_requests
                    too_many_requests_errors = self._429_count[hostname]
                    self.logger.info(f'{hostname}: {requests_per_minute} requests per minute, rate - {rate}, '
                                     f'too many requests count - {too_many_requests_errors}')

                    self._requests_made[hostname] = 0
                    self._requests_successful[hostname] = 0
                    self._429_count[hostname] = 0

    async def _process_request(self, url: str, tries=2, **kwargs) -> dict | None:
        hostname = url.split('//')[1].split('/')[0]
        if hostname in self.cfg["host_without_proxy"]:
            return await self._make_request(hostname, url, **kwargs)

        while True:
            # context manager is used to delete the proxy from the common pool while in use
            async with self._get_proxy(hostname) as proxy:
                try:
                    return await self._make_request(hostname, url, tries=tries, proxy=proxy, **kwargs)
                except TooManyRequests:
                    proxy.last_requests[hostname] = time.time() + self.cfg['jail_time'][hostname]

    async def _make_request(self, hostname: str, url: str, tries=2, proxy: Proxy = None, **kwargs):
        if proxy is not None:
            kwargs["proxy"] = proxy.url

        for _ in range(tries):
            self._requests_made[hostname] += 1
            # all exceptions except TooManyRequests are ignored and a next attempt is started
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, **kwargs) as res:
                        if res is None:
                            continue
                        if res.status == 429 or res.status == 407:  # 407 is a proxy authentication error
                            self._429_count[hostname] += 1
                            raise TooManyRequests
                        if proxy is not None:
                            proxy.last_requests[hostname] = time.time()
                        if res.ok:
                            try:
                                json_res = await res.json()
                            except:
                                json_res = {}
                            text_res = await res.text()

                            result = {
                                'json': json_res,
                                'text': text_res
                            }
                            # this causes inadequate ram consumption
                            # self._cache[url + json.dumps(kwargs)] = result
                            self._requests_successful[hostname] += 1
                            return result
                        return None
            except TooManyRequests:
                raise TooManyRequests
            except Exception as e:
                self.logger.warning(f'could not get {url} - {e}')

    async def _respond_to_request(self, socket, clientid, url, **kwargs):
        use_cached = True
        if 'cached' in kwargs:
            if not kwargs['cached']:
                use_cached = False

            kwargs.pop('cached')

        if url + json.dumps(kwargs) in self._cache and use_cached:
            response = self._cache[url + json.dumps(kwargs)]
        else:
            response = await self._process_request(url, **kwargs)

        await socket.send_multipart([clientid, b'', pickle.dumps(response)])

    async def _run_server(self):
        socket = zmq.asyncio.Context.instance().socket(zmq.ROUTER)
        tasks = set()

        with socket.bind(self.address):
            while True:
                clientid, _, data = await socket.recv_multipart()
                url, kwargs = pickle.loads(data)
                task = asyncio.create_task(self._respond_to_request(socket, clientid, url, **kwargs))
                tasks.add(task)
                task.add_done_callback(tasks.discard)

    @classmethod
    async def get(cls, url, cached=True, **kwargs) -> dict | None:
        """use cached=False to force a new request"""
        kwargs['cached'] = cached

        while cls.cfg['max_sockets'] <= cls._open_sockets:
            await asyncio.sleep(0.01)

        socket = zmq.asyncio.Context.instance().socket(zmq.REQ)
        cls._open_sockets += 1
        socket.connect(cls.address)
        await socket.send(pickle.dumps((url, kwargs)))
        result = pickle.loads(await socket.recv())
        socket.close()
        cls._open_sockets -= 1
        return result


if __name__ == '__main__':
    asyncio.run(RequestHandler().start(), debug=True)
