# edu

小朋友的教学项目：教材、题库、教学资料、复习材料、考题等。

## 背景

- 目标学制：**上海五四学制**（小学 5 年 + 初中 4 年），教材以沪教版/统编版（五四制）为准
- 教材来源：国家中小学智慧教育平台 basic.smartedu.cn 的官方原版 PDF

## 目录结构

```
edu/
├── README.md
├── booklist.json       # smartedu 书目清单(contentId + PDF 地址), 由脚本维护
├── scripts/
│   ├── download_books.py   # 教材批量下载脚本
│   └── README.md           # 下载原理 + 踩坑记录
└── sh_edu/             # 教材库(gitignore, 不入库): <学段>/<年级>/<学科>/xxx.pdf
```

## 教材下载

```bash
# smartedu 官方教材(语文/数学/英语沪教版等)
python3 scripts/download_books.py --refresh
python3 scripts/download_books.py

# 上海低年级英语(牛津上海版, smartedu 不收录, 从 haoduoyun.cc)
python3 scripts/download_haoduoyun_book.py <书页URL> <输出PDF>
```

详见 [scripts/README.md](scripts/README.md)。

当前已下载：
- **小学语数英 24 本**：smartedu 官方 20 本（语文统编 1-5 年级全、数学沪教 1-5 年级上册、英语沪教 3-5 年级上册；数学/英语部分下册平台未发布）+ 牛津上海版英语 4 本（一二年级上下册）
- 上海低年级英语说明：一、二年级用《九年义务教育课本·英语（牛津上海版）》（试用本，上海教育出版社），三年级起用新课标沪教版
