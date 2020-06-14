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

    args = parser.parse_args()

    cust_handler = QueueHandler()
    cust_handler.setFormatter(logging.Formatter(
        datefmt=DATE_FORMAT, fmt=LOG_FORMAT))
    logging.basicConfig(level=logging.DEBUG, handlers=(
        cust_handler,))
    init()

    down = Download(args.name,
                    args.url, process_num=args.process)
    asyncio.run(down.go())
    subprocess.run(["ffmpeg", "-i", args.url.split("/")
                    [-1], "-c", "copy", f"{args.name}.mkv"], cwd=os.path.join("video", args.name))
    logging.info(f'{args.name}\t下载完毕')
