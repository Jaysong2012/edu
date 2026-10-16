#!/usr/bin/env python3
"""把教材 PDF 转成文本，供出复习题/教学材料使用。

两条路线:
1. 文字层路线(数学等): pdftotext 直接提取, 质量完美
2. 图片路线(英语等): pdfimages 抠出每页原图, 喂视觉模型(see-image skill)

用法:
    python3 pdf_to_text.py <pdf路径>              # 有文字层则转 txt 并输出到同结构 txt/ 目录
    python3 pdf_to_text.py <pdf路径> --pages 12,13  # 只转指定页
    python3 pdf_to_text.py <pdf路径> --images 12   # 抠出第12页原始图片到 /tmp

判断有没有文字层: 提取全书文本, 若 < 100 字符(水印除外)视为纯图片。
"""
import os
import re
import subprocess
import sys


def pdftotext(pdf, first=None, last=None):
    cmd = ['pdftotext', '-layout']
    if first:
        cmd += ['-f', str(first)]
    if last:
        cmd += ['-l', str(last)]
    cmd += [pdf, '-']
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout


def out_path_for(pdf):
    """sh_edu/小学/X/Y.pdf -> txt/小学/X/Y.txt (与教材库同结构)"""
    m = re.match(r'(.*)/sh_edu/(.+)\.pdf$', os.path.abspath(pdf))
    if not m:
        return os.path.splitext(pdf)[0] + '.txt'
    return f'{m.group(1)}/txt/{m.group(2)}.txt'


def main():
    pdf = sys.argv[1]
    pages = images = None
    args = sys.argv[2:]
    if '--pages' in args:
        spec = args[args.index('--pages') + 1]
        p = spec.split(',')[0]
        pages = (int(p), int(spec.split(',')[-1]))
    if '--images' in args:
        images = args[args.index('--images') + 1]

    if images:
        # 抠原始图片(比渲染质量高, PDF 里的图是原样嵌入的)
        first = last = images.split(',')[0].split('-')[0]
        r = subprocess.run(['pdfimages', '-png', '-f', first, '-l',
                            images.split(',')[-1].split('-')[-1], pdf, '/tmp/pageimg'],
                           capture_output=True, text=True)
        files = sorted(f for f in os.listdir('/tmp') if f.startswith('pageimg'))
        print('\n'.join(f'/tmp/{f}' for f in files))
        print(f'抠出 {len(files)} 张图, 可直接喂 ~/.claude/skills/see-image/see_image.sh')
        return

    text = pdftotext(pdf, *(pages or (None, None)))
    # 去掉水印行(英语书的 "4ASH00152026秋备案" 之类, -layout 下可能带其他列)
    cleaned = re.sub(r'^\s*[\dA-Za-z]*秋备案\s*[\dA-Za-z]*\s*$', '', text, flags=re.M)
    cleaned = re.sub(r'[\dA-Za-z]*秋备案', '', cleaned)
    # 有效内容 = 汉字字数 + 连续字母片段(单词)数; 水印残片是单个字母+数字, 不计入
    n_han = len(re.findall(r'[一-鿿]', cleaned))
    n_word = len(re.findall(r'[a-zA-Z]{2,}', cleaned))
    if n_han + n_word < 50:
        print(f'纯图片 PDF (有效内容仅 {n_han + n_word}), 走视觉路线: '
              f'python3 {sys.argv[0]} "{pdf}" --images 页码')
        sys.exit(2)

    out = out_path_for(pdf)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w').write(cleaned)
    print(f'{out} (汉字 {n_han} + 单词 {n_word})')


if __name__ == '__main__':
    main()
