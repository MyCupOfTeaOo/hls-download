import aiohttp
import asyncio
from fake_useragent import UserAgent
import os
import re
import logging
import aiofiles
import signal
import sys
import json
import traceback

TIMEOUT = 20

PROXY = {'http': 'http://127.0.0.1:1080',
         'https': 'https://127.0.0.1:1080', 'ftp': 'ftp://127.0.0.1:1080'}

ts_pattern = re.compile(r"(?<=\n)[0-9]+.ts(?=\n|$)")


def get_user_agent():
    ua = UserAgent()
    return ua.random


class Download():
    _m3u8_url = ""
    _list_url = []
    _downloading_url = []
    _wait_down_url = []
    error_count = 0

    def __init__(self, name, list_url, process_num=10):
        self._m3u8_url = list_url
        self.process_num = process_num
        self._name = name
        self._root_url = "/".join(list_url.split('/')[:-1])
        self._path = f'video/{name}'

    async def go(self):
        signal.signal(signal.SIGTERM, self.write_log)
        signal.signal(signal.SIGINT, self.write_log)
        asyncio.ensure_future(self.monitor())
        if os.path.exists(f'{self._path}/log.json'):
            logging.debug(f'检测到历史下载记录,重新构建队列')
            with open(f'{self._path}/log.json', encoding="utf-8", mode="r") as f:
                log = json.loads(f.read())
                self._list_url = log["wait_urls"]
                self._wait_down_url = self._list_url.copy()
            await asyncio.gather(*[self.uid_process() for i in range(self.process_num)])
        else:
            await self.parse_list()

    async def monitor(self):
        logging.info(f'总共:\t {len(self._list_url)}')
        logging.info(f'已下载:\t {len(self._list_url) - len(self._wait_down_url)}')
        logging.info(f'待下载:\t {len(self._wait_down_url)}')
        logging.info(f'正在下载:\t {len(self._downloading_url)}')
        logging.info(f'失败次数:\t {self.error_count}')
        await asyncio.sleep(5)
        asyncio.ensure_future(self.monitor())

    def write_log(self, signum, frame):
        logging.debug('检测到退出信号,准备写日志')
        with open(f'{self._path}/log.json', "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "wait_urls": self._wait_down_url + self._downloading_url,
                "error_count": self.error_count
            }, ensure_ascii=False,
                indent=2, separators=(',', ':')))
        sys.exit(1)

    async def parse_list(self):
        headers = {'user-agent': get_user_agent()}
        async with aiohttp.ClientSession() as session:
            async with session.get(self._m3u8_url, headers=headers, timeout=TIMEOUT, proxy=PROXY["http"]) as res:
                list_text = await res.text()
                self.create_file(self._m3u8_url.split('/')[-1], list_text)
                self._list_url = ts_pattern.findall(list_text)
                self._wait_down_url = self._list_url.copy()
                await asyncio.gather(*[self.uid_process() for i in range(self.process_num)])

    async def uid_process(self):
        uid = self._wait_down_url.pop(0)
        self._downloading_url.append(uid)
        if uid:
            url = f'{self._root_url}/{uid}'
            logging.debug(f'开始下载 {url}')
            result = await self.down_file(uid, url)
            if result:
                self._downloading_url.remove(uid)
                logging.debug(f'{uid} 下载成功')
            else:
                logging.error(f'{uid} 下载失败')
                self.error_count += 1
                self._wait_down_url.append(uid)
                self._downloading_url.remove(uid)
            await self.uid_process()

    async def down_file(self, name, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=TIMEOUT, proxy=PROXY["http"]) as res:
                    if res.status == 200:
                        async with aiofiles.open(f'{self._path}/{name}', mode="wb") as f:
                            await f.write(await res.read())
                            return True
        except:
            logging.error(traceback.format_exc())
            return False

    def create_file(self, filename, text):
        if not os.path.exists(self._path):
            os.makedirs(self._path)
        filepath = f'{self._path}/{filename}'
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
