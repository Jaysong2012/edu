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
# 首次/更新书目
python3 scripts/download_books.py --refresh

# 批量下载(已有跳过, 签名头过期自动刷新)
python3 scripts/download_books.py
python3 scripts/download_books.py --stage 小学 --subject 数学
```

前置条件与原理详见 [scripts/README.md](scripts/README.md)。

当前已下载：小学 语文/数学/英语 20 本（数学三、四、五年级下册及英语下册平台未发布，待更新后增量下载）。
