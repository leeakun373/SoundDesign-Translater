# 音频术语库（Glossary）

## 你是用户

**只需维护：**

- `glossary/user_overrides.csv` — 英↔中覆盖、不译规则
- `glossary/zh_oral_aliases.csv` — 中→英口语（可选）

改完运行：

```bash
python glossary/build_glossary.py
```

## 文件说明

| 文件 | 谁改 | 作用 |
|------|------|------|
| `user_overrides.csv` | **你** | 最高优先级 |
| `zh_oral_aliases.csv` | **你** | 中→英口语 |
| `sources/*.csv` | 随仓库 | UCS/MyKeyWord 底库 |
| `build_glossary.py` | 开发 | 合并 → SQLite |
| `audio_glossary.sqlite` | 自动生成 | 运行时查表 |

## user_overrides.csv 格式

```csv
en,zh,term_type,action,note
Room Tone,房间底噪,keyword,translate,优先于机翻
ICEFric,,catid,never_translate,CatID 不译
```

- `action=translate`：强制翻译
- `action=never_translate`：文件名/句子中保持原样

## 底库合并顺序

1. `user_overrides.csv`
2. `sources/MyKeyWordV1.csv`
3. `sources/ucs_catid_list.csv`
4. `sources/ucs_categorylist.csv`

详见项目根 [README.md](../README.md)。
