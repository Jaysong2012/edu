#!/usr/bin/env python3
"""批量下载国家中小学智慧教育平台(smartedu)电子教材 PDF。

用法:
    python3 download_books.py                      # 按 booklist.json 全量下载(跳过已有)
    python3 download_books.py --stage 小学          # 只下某学段
    python3 download_books.py --subject 数学        # 只下某学科
    python3 download_books.py --refresh            # 重新抓取书目并覆盖 booklist.json
    python3 download_books.py '<x-nd-auth头>'      # 显式传入签名头(避免先开浏览器)

前置条件:
    1. 主浏览器(Chrome)已登录 basic.smartedu.cn 且保持运行(签名头从登录态页面刷新)
    2. playwright-cli 全局可用

输出目录: <脚本上级目录>/sh_edu/<学段>/<年级>/<学科>/<学科><年级><册次>.pdf
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
EDU = os.path.dirname(BASE)
BOOKLIST = f'{EDU}/booklist.json'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36')
PC = ['playwright-cli', '-s=userchrome']
PC_QUIET = PC + ['--raw']

# 目录数据源: data_version.json 里的 part 文件按 tag 过滤
TAG_HOST = 'https://s-file-2.ykt.cbern.com.cn/zxx/ndrs'
# 目标标签维度: 学段 zxxxd / 学科 zxxxk / 版本 zxxbb / 年级 zxxnj / 册次 zxxcc
DEFAULT_FILTER = {
    'zxxxd': '小学（五•四学制）',
    'zxxxk': ['语文', '数学', '英语'],
    'zxxbb': ['统编版', '沪教版'],
}
GRADE_ORDER = ['一年级', '二年级', '三年级', '四年级', '五年级',
               '六年级', '七年级', '八年级', '九年级']


def http_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return json.load(urllib.request.urlopen(req, timeout=30))


def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ---------- 书目抓取 ----------

def fetch_booklist():
    """从平台静态目录拉全量书目, 按标签过滤, 写入 booklist.json。"""
    ver = http_json(f'{TAG_HOST}/resources/tch_material/version/data_version.json')
    items = []
    for url in ver['urls'].split(','):
        items.extend(http_json(url.strip()))
    print(f'全量教材条目: {len(items)}')

    books = []
    for it in items:
        tags = {t['tag_dimension_id']: t['tag_name'] for t in it.get('tag_list', [])}
        f = DEFAULT_FILTER
        if tags.get('zxxxd') != f['zxxxd']:
            continue
        if tags.get('zxxxk') not in f['zxxxk'] or tags.get('zxxbb') not in f['zxxbb']:
            continue
        books.append({
            'id': it['id'],
            'title': it.get('global_title', {}).get('zh-CN', ''),
            'stage': tags.get('zxxxd'),
            'subject': tags.get('zxxxk'),
            'publisher': tags.get('zxxbb'),
            'grade': tags.get('zxxnj'),
            'volume': tags.get('zxxcc'),
            'status': it.get('status'),
        })

    # 每本书取 PDF 真实地址
    for b in books:
        d = http_json(f'{TAG_HOST}/../ndrv2/resources/tch_material/details/{b["id"]}.json')
        pdfs = [s for item in d.get('ti_items', [])
                for s in item.get('ti_storages', []) if s.endswith('.pdf')]
        b['pdf_urls'] = pdfs

    books.sort(key=lambda b: (
        b['subject'], GRADE_ORDER.index(b['grade']), b['volume'] or ''))
    json.dump(books, open(BOOKLIST, 'w'), ensure_ascii=False, indent=1)
    print(f'匹配书目: {len(books)}, 已写入 {BOOKLIST}')
    return books


# ---------- 签名头 ----------

def refresh_auth():
    """驱动登录态浏览器打开一个详情页, 从 pdfjs 请求中抓新的 x-nd-auth 头。

    原理: 详情页内嵌 pdfjs 阅读器(iframe), 其对 CDN 的 GET 会带页面 JS 现算的
    MAC 签名头; 该头不绑定 URL, 抓一个即可给 curl 复用, 但 nonce 带时间戳会过期。
    """
    books = json.load(open(BOOKLIST))
    b = books[0]
    url = ('https://basic.smartedu.cn/tchMaterial/detail?contentType=assets_document'
           f"&contentId={b['id']}&catalogType=tchMaterial&subCatalog=tchMaterial")
    # 确保 CDP 已连上主浏览器(会话可能已 detach)
    probe = run(PC + ['tab-list'], timeout=60)
    if probe.returncode != 0 or 'smartedu' not in probe.stdout and 'http' not in probe.stdout:
        run(['playwright-cli', '-s=userchrome', 'attach', '--cdp=chrome'], timeout=120)
    run(PC + ['goto', url], timeout=90)
    for _ in range(20):
        time.sleep(3)
        out = run(PC_QUIET + ['requests'], timeout=60).stdout
        ids = re.findall(
            r'^(\d+)\. \[GET\] https://r\d-ndr-private\.ykt\.cbern\.com\.cn/edu_product/esp/assets/.*\.pdf',
            out, re.M)
        if ids:
            detail = run(PC_QUIET + ['request', ids[-1]], timeout=60).stdout
            m = re.search(r'x-nd-auth:\s*(.+)', detail)
            if m:
                auth = m.group(1).strip()
                print(f'[auth] 已刷新签名头', flush=True)
                return auth
    raise RuntimeError('无法刷新签名头: 20 次未捕获到 pdfjs 的 PDF 请求, '
                       '检查主浏览器是否登录且 playwright-cli 可连接')


# ---------- 下载 ----------

def is_pdf(path):
    if not os.path.exists(path):
        return False
    with open(path, 'rb') as f:
        return f.read(5) == b'%PDF-'


def curl_download(url, auth, out_path):
    r = subprocess.run([
        'curl', '-sL', '-o', out_path, '-w', '%{http_code}',
        '-H', f'x-nd-auth: {auth}',
        '-H', 'Referer: https://basic.smartedu.cn/',
        '-H', f'User-Agent: {UA}',
        '--max-time', '600', url
    ], capture_output=True, text=True, timeout=660)
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('auth', nargs='?', help='显式传入 x-nd-auth 头')
    ap.add_argument('--stage', help='按学段过滤, 如 小学')
    ap.add_argument('--subject', help='按学科过滤, 如 数学')
    ap.add_argument('--refresh', action='store_true', help='重新抓取书目')
    args = ap.parse_args()

    if args.refresh or not os.path.exists(BOOKLIST):
        books = fetch_booklist()
    else:
        books = json.load(open(BOOKLIST))

    if args.stage:
        # 兼容旧 booklist(无 stage 字段): 默认都是小学
        books = [b for b in books if args.stage in b.get('stage', '小学')]
    if args.subject:
        books = [b for b in books if b.get('subject') == args.subject]

    auth = args.auth  # 惰性获取: 全部 SKIP 时不打扰浏览器
    ok, fail = [], []
    for i, b in enumerate(books):
        fname = f"{b['subject']}{b['grade']}{b['volume']}.pdf"
        stage = b.get('stage', '小学（五•四学制）').replace('（五•四学制）', '')
        out_path = f"{EDU}/sh_edu/{stage}/{b['grade']}/{b['subject']}/{fname}"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        url = next((u for u in b['pdf_urls'] if u.startswith('https://r')), None)
        if not url:
            print(f"[{i+1}/{len(books)}] 无PDF地址 {fname}", flush=True)
            fail.append(fname)
            continue
        if is_pdf(out_path):
            print(f'[{i+1}/{len(books)}] SKIP {fname}', flush=True)
            ok.append(fname)
            continue
        for attempt in range(3):
            if not auth:
                auth = refresh_auth()
            code = curl_download(url, auth, out_path)
            if code in ('200', '206') and is_pdf(out_path):
                size = os.path.getsize(out_path)
                print(f'[{i+1}/{len(books)}] OK   {fname} {size/1e6:.1f}MB', flush=True)
                ok.append(fname)
                break
            print(f'[{i+1}/{len(books)}] RETRY {fname} code={code} attempt={attempt+1}', flush=True)
            auth = refresh_auth()
        else:
            print(f'[{i+1}/{len(books)}] FAIL {fname}', flush=True)
            fail.append(fname)

    print(f'\n完成: {len(ok)} 成功, {len(fail)} 失败')
    if fail:
        print('失败列表:', fail)
        sys.exit(1)


if __name__ == '__main__':
    main()
