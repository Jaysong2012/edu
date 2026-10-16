# smartedu 教材下载工具

从国家中小学智慧教育平台(basic.smartedu.cn)批量下载电子教材 PDF，已跑通上海五四学制小学语数英 20 本。

## 目录结构

```
edu/
├── booklist.json                    # smartedu 书目清单(contentId + PDF地址)
├── scripts/
│   ├── download_books.py            # smartedu 官方教材批量下载
│   ├── download_haoduoyun_book.py   # 好多电子课本网(haoduoyun.cc)整本下载, 合成 PDF
│   └── README.md                    # 本文档
└── sh_edu/                          # 教材库: <学段>/<年级>/<学科>/xxx.pdf
```

## 使用方法

**脚本一：smartedu 官方教材**（前置：主浏览器已登录 basic.smartedu.cn 并保持运行）

```bash
python3 scripts/download_books.py --refresh          # 首次/更新书目
python3 scripts/download_books.py                    # 全量下载(已有跳过)
python3 scripts/download_books.py --stage 小学 --subject 数学
```

**脚本二：haoduoyun.cc 地方教材**（无需登录，上海低年级英语牛津上海版等 smartedu 不收录的书）

```bash
python3 scripts/download_haoduoyun_book.py <书目录页URL> <输出PDF>
# 例: 牛津上海版一年级英语上册
python3 scripts/download_haoduoyun_book.py \
  'https://m.haoduoyun.cc/book/hjb/yingyu/jr1a.shtml' \
  'sh_edu/小学/一年级/英语/英语一年级上册（牛津上海版）.pdf'
```

已下载的牛津上海版页面代码（沪教版 hjb/yingyu/ 下）：

| 年级 | 上册 | 下册 |
|---|---|---|
| 一年级 | `jr1a` | `rk1b` |
| 二年级 | `ky2a` | `jk2b` |

注意：三~五年级英语用 smartedu 的沪教版(新课标)，低年级才是牛津上海版旧教材。

## 下载原理

1. **书目目录**是纯静态 JSON，匿名可拉：
   - 标签树 `s-file-2.ykt.cbern.com.cn/zxx/ndrs/tags/tch_material_tag.json`
   - 全量书目 `.../resources/tch_material/version/data_version.json` → 指向 part_100~103.json
   - 每本书详情 `.../ndrv2/resources/tch_material/details/{contentId}.json` → `ti_items[].ti_storages[]` 里有 PDF 真实地址
2. **PDF 在私有 CDN**(`r1-ndr-private.ykt.cbern.com.cn`)，匿名 GET 一律 401。鉴权靠页面 JS 现算的请求头：
   ```
   x-nd-auth: MAC id="...",nonce="<毫秒时间戳:随机串>",mac="..."
   ```
3. 关键突破口(实测)：**该签名头不绑定 URL**——从登录态浏览器抓一个，curl 即可直拉任意书。但 nonce 带时间戳，会过期(实测约几十分钟)，脚本在 401 时自动重开详情页刷新。
4. 签名头获取方式：`playwright-cli attach --cdp=chrome` 连登录态主浏览器 → 打开任一详情页 → pdfjs 阅读器会对 CDN 发带签名的 GET → 从请求详情里抓头。

## 踩坑记录

### smartedu (download_books.py)

| 坑 | 现象 | 原因/解法 |
|---|---|---|
| 直接 curl PDF 401 | `openresty 401 Authorization Required` | 缺 `x-nd-auth` 签名头；补头后即使 curl 也通 |
| 加 Origin/Referer/Cookie 仍 401 | 各种伪装都过不去 | WAF 还校验请求指纹，别在头之外浪费时间，直接走签名头方案 |
| `teach/api_static/trains/tchMaterial.json` 403 | curl 和浏览器都拿不到 | 该静态文件已废弃/收紧，用 `ndrs/resources/tch_material/` 新路径 |
| 页内 fetch PDF 偶尔 200 偶尔 401 | HEAD 通 GET 不通 | 没登录时只有部分请求侥幸过；登录态 + 签名头才稳定 |
| 跨域 fetch 带 cookie 失败 | `TypeError: Failed to fetch` | CDN 域不带 CORS 凭证；用 pdfjs iframe(同源)读 `PDFViewerApplication.pdfDocument.getData()` 可拿整本字节——单本应急方案 |
| 标签树解析只剩 9 条链 | 遍历提前断链 | 叶子在 `hierarchies[].children` 为空处，同一 tag 的 `hierarchies` 可能既有子又有空，两层都要判 |
| 下册缺文件 | 如数学三/四/五年级下册 | **平台没发布**，不是下载失败；`booklist.json` 里能看哪些有 `pdf_urls` |
| 牛津上海版搜不到 | 全量目录 0 命中 | 国家平台不收录上海低年级英语地方教材(牛津上海版试用本)，走 haoduoyun 脚本 |

### haoduoyun (download_haoduoyun_book.py)

| 坑 | 现象 | 原因/解法 |
|---|---|---|
| 书目录页没有 totalPage | 解析不到总页数 | 变量在内页；脚本会先探测一个单元内页 |
| 内页 URL 拼错 | 全部"无图片, 跳过" | 书目录页 `foo.shtml` 的内页在 `foo/{n}.shtml` 子目录，不是同级 |
| 页面代码无规律 | 一上是 jr1a、一下是 rk1b、二上是 ky2a、二下是 jk2b | 不猜，用搜索引擎(site:haoduoyun.cc 书名)定位 |
| 图片是压缩图 | mmbiz.qpic.cn 的 640 宽 | URL 里 `/640` 换 `/0` 得到 1280 宽原图 |
| 页面 UA 检测 | 桌面 UA 会 302 跳主站 | 请求带手机 UA |
| 图片来源不统一 | 有的书走 1010pic.com, 有的走微信 CDN | 脚本按 `ebookPage('URL')` 逐页取，不依赖单一域名 |

## 标签维度速查

标签树五级链(维度 id → 含义)：`zxxxd`学段 → `zxxxk`学科 → `zxxbb`版本 → `zxxnj`年级 → `zxxcc`册次。

上海五四学制相关取值：学段 `小学（五•四学制）`/`初中（五•四学制）`；语文=统编版、数学英语=沪教版(青岛版/鲁科版是山东的，别下混)。

## 单本应急方案(不跑脚本)

浏览器打开详情页 → console 执行(iframe 同源)：
```js
const app = document.querySelector('iframe').contentWindow.PDFViewerApplication;
const data = await app.pdfDocument.getData();
// 再 POST 到本地接收服务落盘(见 git 历史里的 recv_pdf.py 思路)
```
