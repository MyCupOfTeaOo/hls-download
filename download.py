import aiohttp
import asyncio
# from fake_useragent import UserAgent
import os
import re
import logging
import aiofiles
import signal
import sys
import json
import glob
import traceback
from urllib.parse import urljoin

TIMEOUT = 20


ts_pattern = re.compile(r"(?<=\n)(\S+.ts|\S+.ts\?.+)(?=\n|$)")
key_pattern = re.compile(r"(?<=URI\=\")\S+.(ts|key)(?=\")")
file_suffix = re.compile(r"\..*")
name_filter_pattern = re.compile(r"\?.*")


def get_user_agent():
    # ua = UserAgent()
    # return ua.random
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"


class Download():
    _m3u8_url = ""
    _list_uid = []
    _downloading_uid = []
    _wait_down_uid = []
    _error_count = 0
    _consecutive_error_count = 0

    def __init__(self, name, list_url, proxy=None, process_num=10):
        self._m3u8_url = list_url
        self._proxy = proxy
        self.process_num = process_num
        self._name = name
        self._root_url = "/".join(list_url.split("?")[0].split('/')[:-1]) + "/"
        self._path = f'video/{name}'

    async def go(self):
        signal.signal(signal.SIGTERM, self.registry_exit_callback)
        signal.signal(signal.SIGINT, self.registry_exit_callback)
        asyncio.ensure_future(self.monitor())
        if os.path.exists(f'{self._path}/log.json'):
            logging.debug(f'检测到历史下载记录,重新构建队列')
            await self.refactor_list()
        else:
            await self.parse_list()

    async def monitor(self):
        logging.info(f'总共:\t {len(self._list_uid)}')
        logging.info(
            f'已下载:\t {len(self._list_uid) - len(self._wait_down_uid)}')
        logging.info(f'待下载:\t {len(self._wait_down_uid)}')
        logging.info(f'正在下载:\t {len(self._downloading_uid)}')
        logging.info(f'失败次数:\t {self._error_count}')
        if (self._consecutive_error_count > 20):
            logging.error("连续下载失败过多,退出程序")
            self.registry_exit_callback(1, 1)
        await asyncio.sleep(5)
        asyncio.ensure_future(self.monitor())

    def registry_exit_callback(self, signum, frame):
        logging.debug('检测到退出信号,准备写日志')
        self.write_log()
        os._exit(0)

    def write_log(self):
        with open(f'{self._path}/log.json', "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "wait_urls": self._wait_down_uid + self._downloading_uid,
                "_error_count": self._error_count,
                "last_m3u8": name_filter_pattern.sub("", self._m3u8_url.split("?")[0].split('/')[-1])
            }, ensure_ascii=False,
                indent=2, separators=(',', ':')))

    async def refactor_list(self):
        headers = {'user-agent': get_user_agent()}
        async with aiohttp.ClientSession() as session:
            async with session.get(self._m3u8_url, headers=headers, timeout=TIMEOUT, proxy=self._proxy) as res:
                list_text = await res.text()
                if (res.status > 300):
                    logging.error(list_text)
                    os._exit(0)
                with open(f'{self._path}/log.json', encoding="utf-8", mode="r") as f:
                    log = json.loads(f.read())
                with open(f'{self._path}/{log.get("last_m3u8")}', encoding="utf-8", mode="r") as f:
                    last_m3u8 = f.read()
                last_list_uid = ts_pattern.findall(last_m3u8)
                list_url = ts_pattern.findall(list_text)
                if last_list_uid[0] != list_url[0]:
                    logging.warning("检测到uid变动,重构uid")
                    old_list_uid = log["wait_urls"]
                    new_list_uid = list(
                        map(lambda old_uid: list_url[last_list_uid.index(old_uid)], old_list_uid))
                    # key
                    key_res = key_pattern.search(list_text)
                    key = None
                    if key_res:
                        key = key_res.group()
                    self.create_file(
                        self._m3u8_url, list_text + '\n#EXT-X-ENDLIST')
                    if key:
                        if not await self.down_file(file_suffix.sub(".ts", key), urljoin(self._root_url, key)):
                            raise RuntimeError("下载key文件失败")
                    os.remove(f'{self._path}/{log.get("last_m3u8")}')

                    self._list_uid = new_list_uid
                    self._wait_down_uid = self._list_uid.copy()
                else:
                    self._list_uid = log["wait_urls"]
                    self._wait_down_uid = self._list_uid.copy()
                await asyncio.gather(*[self.uid_process() for i in range(self.process_num)])
                # 回写日志,防止重下载
                self.write_log()

    async def parse_list(self):
        headers = {'user-agent': get_user_agent()}
        async with aiohttp.ClientSession() as session:
            async with session.get(self._m3u8_url, headers=headers, timeout=TIMEOUT, proxy=self._proxy) as res:
                list_text = await res.text()
                if (res.status > 300):
                    logging.error(list_text)
                    os._exit(0)
                # key
                key_res = key_pattern.search(list_text)
                key = None
                if key_res:
                    key = key_res.group()
                self.create_file(name_filter_pattern.sub(
                    "", self._m3u8_url), list_text + '\n#EXT-X-ENDLIST')
                if key:
                    if not await self.down_file(key, urljoin(self._root_url, key)):
                        raise RuntimeError("下载key文件失败")
                self._list_uid = ts_pattern.findall(list_text)
                self._wait_down_uid = self._list_uid.copy()
                await asyncio.gather(*[self.uid_process() for i in range(self.process_num)])
                # 回写日志,防止重下载
                self.write_log()

    async def uid_process(self):
        if len(self._wait_down_uid) < 1:
            return
        uid = self._wait_down_uid.pop(0)
        self._downloading_uid.append(uid)
        url = urljoin(self._root_url, uid)
        logging.debug(f'开始下载 {url}')
        result = await self.down_file(uid, url)
        if result:
            self._consecutive_error_count = 0
            self._downloading_uid.remove(uid)
            logging.debug(f'{uid} 下载成功')
        else:
            logging.error(f'{uid} 下载失败')
            self._error_count += 1
            self._consecutive_error_count += 1
            self._wait_down_uid.append(uid)
            self._downloading_uid.remove(uid)
        await self.uid_process()

    async def down_file(self, name, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=TIMEOUT, proxy=self._proxy) as res:
                    if res.status == 200:
                        async with aiofiles.open(f'{self._path}/{name_filter_pattern.sub("",name.split("?")[0].split("/")[-1])}', mode="wb") as f:
                            await f.write(await res.read())
                            return True
        except:
            logging.error(traceback.format_exc())
            return False

    def create_file(self, filename, text):
        if not os.path.exists(self._path):
            os.makedirs(self._path)
        filepath = f'{self._path}/{name_filter_pattern.sub("",filename.split("?")[0].split("/")[-1])}'
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
