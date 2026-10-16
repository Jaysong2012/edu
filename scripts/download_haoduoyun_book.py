#!/usr/bin/env python3
"""从好多电子课本网(haoduoyun.cc)下载整本教材并合成 PDF。

用法:
    python3 download_haoduoyun_book.py <书页URL> <输出PDF路径> [总页数]

示例(牛津上海版二年级英语上册, 上海低年级英语地方教材, smartedu 无收录):
    python3 download_haoduoyun_book.py \
        'https://m.haoduoyun.cc/book/hjb/yingyu/ky2a.shtml' \
        'sh_edu/小学/二年级/英语/英语二年级上册（牛津上海版）.pdf'

原理: 书目录页 var iPage=...,totalPage=N 给出总页数;
每页 <url>/<页码>.shtml 的 ebookPage('图片URL') 给出该页真实图片(微信CDN);
把 URL 里 /640 换成 /0 可取未压缩原图。
"""
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')


def download(url, path):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    data = urllib.request.urlopen(req, timeout=60).read()
    with open(path, 'wb') as f:
        f.write(data)
    return len(data)


def main():
    index_url, out_pdf = sys.argv[1], sys.argv[2]
    total = int(sys.argv[3]) if len(sys.argv) > 3 else None

    # 内页路径: 书目录页 foo.shtml -> foo/{n}.shtml; 单元页 foo/2.shtml -> foo/{n}.shtml
    if re.search(r'/([a-z0-9]+)\.shtml$', index_url):
        base = index_url[:-len('.shtml')]
    else:
        base = index_url.rsplit('/', 1)[0]
    html = get(index_url)
    m = re.search(r'totalPage=(\d+)', html) if not total else None
    if not m and not total:
        # 目录页没有 totalPage, 从任一单元内页探测
        m2 = re.search(r'href="(/book/[^"]+/\d+\.shtml)"', html)
        if m2:
            probe = get(f"https://m.haoduoyun.cc{m2.group(1)}")
            m = re.search(r'totalPage=(\d+)', probe)
    if m:
        total = int(m.group(1))
    if not total:
        sys.exit('无法从页面解析 totalPage, 请显式传入总页数')

    print(f'总页数: {total}')
    tmpdir = tempfile.mkdtemp(prefix='hdy_book_')
    pages = []
    for n in range(1, total + 1):
        try:
            page_html = get(f'{base}/{n}.shtml')
        except Exception as e:
            print(f'  p{n}: 页面获取失败 {e}')
            continue
        m = re.search(r"ebookPage\('([^']+)'", page_html)
        if not m:
            print(f'  p{n}: 无图片, 跳过')
            continue
        img = m.group(1).replace('/640', '/0')  # /0 = 未压缩原图
        path = f'{tmpdir}/{n:03d}.jpg'
        try:
            size = download(img, path)
            pages.append(path)
            print(f'  p{n}: {size//1024}KB', flush=True)
        except Exception as e:
            print(f'  p{n}: 下载失败 {e}', flush=True)

    if not pages:
        sys.exit('一页都没下到')

    # PIL 合成 PDF(JPEG 直存, 不重编码)
    from PIL import Image
    imgs = [Image.open(p).convert('RGB') for p in sorted(pages)]
    os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
    imgs[0].save(out_pdf, save_all=True, append_images=imgs[1:], quality=90)
    print(f'完成: {out_pdf} ({len(imgs)} 页, {os.path.getsize(out_pdf)//1024//1024}MB)')


if __name__ == '__main__':
    main()
