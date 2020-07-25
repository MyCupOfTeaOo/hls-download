from download import Download
import asyncio
import sys
import logging
from colorama import init
from termcolor import colored
import re
import argparse
import subprocess
import os
import glob

_suffix = re.compile('\n$')

LOG_FORMAT = "%(asctime)s %(name)s-%(levelname)s(%(filename)s:%(funcName)s): %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class QueueHandler(logging.Handler):

    def emit(self, record):
        if not record.getMessage() or record.getMessage() == '\n' or record.getMessage() == '\r\n':
            return
        if(record.levelname == 'ERROR'):
            print(colored(_suffix.sub('', self.format(record), 1), 'red'))
        elif (record.levelname == 'INFO'):
            print(colored(_suffix.sub('', self.format(record), 1), 'green'))
        elif (record.levelname == 'WARNING'):
            print(colored(_suffix.sub('', self.format(record), 1), 'yellow'))
        else:
            print(colored(_suffix.sub('', self.format(record), 1), 'cyan'))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("name", help="下载后的片名,文件会下载到video下")
    parser.add_argument("url", help="m3u8文件地址")
    parser.add_argument("-p", "--process",
                        help="下载进程数,默认5", type=int, default=5)
    parser.add_argument("--proxy",
                        help="代理地址,默认http://127.0.0.1:1080", default="http://127.0.0.1:1080")
    parser.add_argument("--no-proxy", action="store_true",
                        help="关闭代理")

    args = parser.parse_args()

    cust_handler = QueueHandler()
    cust_handler.setFormatter(logging.Formatter(
        datefmt=DATE_FORMAT, fmt=LOG_FORMAT))
    logging.basicConfig(level=logging.DEBUG, handlers=(
        cust_handler,))
    init()
    down = Download(args.name,
                    args.url, proxy=args.proxy if not args.no_proxy else None, process_num=args.process)
    asyncio.run(down.go())

    sp = subprocess.run(["ffmpeg", "-i", args.url.split("/")
                          [-1], "-c", "copy", f"{args.name}.mkv"], cwd=os.path.join("video", args.name))
    if sp.returncode != 0:
        logging.error("合并异常")
    else:
        # 删除原始文件
        for filepath in glob.glob(f"video/{args.name}/*.ts"):
            os.remove(filepath)
        for filepath in glob.glob(f"video/{args.name}/*.m3u8"):
            os.remove(filepath)
        for filepath in glob.glob(f"video/{args.name}/*.json"):
            os.remove(filepath)
        logging.info(f'{args.name}\t下载完毕')
