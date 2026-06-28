# CC-CEDICT 中英词典（备份字典）

社区维护的免费中英词典，作为本项目的 **backup 中英词典**：纯文本、易解析、覆盖简繁中文，带拼音和英文释义。

## 文件

| 文件 | 说明 |
|------|------|
| `cedict_ts.u8` | 解压后的词典正文（UTF-8，`ts` 繁简格式） |
| `cedict_1_0_ts_utf-8_mdbg.txt.gz` | MDBG 官方原始压缩包（保留以便校验/重下） |

## 本次快照

- 版本：`1.0`（format=ts, charset=UTF-8）
- 词条数：**125,056**
- 数据日期：2026-06-28
- 来源 URL：<https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz>

## 格式

每行一个词条（`#` 开头为注释/元数据）：

```
繁體 简体 [pin1 yin1] /释义1/释义2/.../
```

示例：

```
3D打印機 3D打印机 [san1 D da3 yin4 ji1] /3D printer/
```

解析正则参考：

```
^(\S+)\s(\S+)\s\[([^\]]*)\]\s/(.*)/$
```

- group1 = 繁体，group2 = 简体，group3 = 拼音（数字声调），group4 = `/` 分隔的英文释义

## 许可

CC-CEDICT 以 **CC BY-SA 4.0** 发布，发布方 MDBG，参考作品 CEDICT (© 1997–1998 Paul Andrew Denisowski)。

- 许可证：<https://creativecommons.org/licenses/by-sa/4.0/>
- 项目页：<https://cc-cedict.org/wiki/>

使用本数据需保留署名，衍生数据需以相同许可分享。

## 更新方法

```powershell
$url='https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz'
Invoke-WebRequest -Uri $url -OutFile cedict_1_0_ts_utf-8_mdbg.txt.gz -UseBasicParsing
# 解压为 cedict_ts.u8
```
