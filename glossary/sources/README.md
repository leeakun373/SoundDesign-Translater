# 术语库底库 CSV（随仓库分发，build 时自动合并）

| 文件 | 说明 |
|------|------|
| `MyKeyWordV1.csv` | 自整理音效关键词 |
| `ucs_catid_list.csv` | UCS CatID 列表 |
| `ucs_categorylist.csv` | UCS 官方分类同义词 |

覆盖路径（可选）：

```bash
set GLOSSARY_MY_KEYWORD=path/to/MyKeyWordV1.csv
set GLOSSARY_UCS_CATID=path/to/ucs_catid_list.csv
set GLOSSARY_UCS_OFFICIAL=path/to/ucs_categorylist.csv
```

合并脚本：`python glossary/build_glossary.py` → 生成 `glossary/audio_glossary.sqlite`
