# hls 流下载器

要用此下载器必须要有 python3.7 环境与 ffmpeg 环境

## 安装依赖

`pip install -r requirements.txt`

## 运行

> 用来下载 m3u8 视频的,可以下载完成后用 ffmpeg 拼接

`python app.py {下载后的文件夹名} {m3u8地址} [-p] 下载并发数 [--proxy] 你的代理地址,默认http://127.0.0.1:1080 [--no-proxy,关闭代理]`

查看帮助
`python app.py -h`

- [x] 支持退出后可继续下载(可以随时 `ctrl + c` 退出,然后再次运行继续下载,name 不变即可)
- [x] 支持 m3u8 文件变更后继续下载(只是 m3u8 文件和 ts 文件名变了,但是切片内容没有变化)(name 不变使用变更后的 m3u8 url 重新执行)
- [x] 支持代理 
