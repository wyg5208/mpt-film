# TTS 声音与脚本语言不匹配

选了一个无法朗读脚本语言的声音时，管线不会得到一个普通的"网络错误"，而是两种特殊的失败形态。
本文说明原因、本次迭代后的系统行为，以及如何避免。

---

## 1. 两种失败形态

| 形态 | 触发条件 | 原始表现 |
|---|---|---|
| **零字节音频** | 脚本完全不可读（如 `af-ZA-AdriNeural` + 纯中文脚本） | edge-tts 在服务端正常握手但收到 0 字节音频流，抛 `NoAudioReceived`。2026-11-09 之前被当作瞬时错误重试 3 次，最终报"检查 TTS 连接"——误导排查方向 |
| **近空音频** | 脚本夹少量可读内容（如中文脚本里的英文单词 "Agent"） | 声音只朗读那些片段，产出几秒音频，任务"成功"，成片时长跟随音频——得到一个几秒钟的近空视频，**没有任何报错** |

共同根因：**声音的语言区域 ≠ 脚本语言**。网络、代理、edge-tts 版本均无关（已用 2×2 实验交叉验证：同一声音配英文正常、zh-CN 声音配中文正常）。

---

## 2. 现在的系统行为

### 2.1 零字节音频：快速失败

`app/services/voice.py` `azure_tts_v1` 单独捕获 `NoAudioReceived`：只尝试 **1 次**（重试不会改变确定性结果），日志点名声音并提示语言不匹配；其他异常仍保留 3 次重试。任务失败信息带上声音名：

```text
failed to synthesize audio with voice 'af-ZA-AdriNeural'; verify the voice
matches the script language and TTS connectivity
```

### 2.2 近空音频：时长健全性守卫

`app/services/task.py` `generate_audio` 在音频时长测算后检查：

- **触发**：脚本 CJK 字符数（`[\u4e00-\u9fff]`）> 50 且实测音频时长（取整前）< 5.0 秒；
- **行为**：任务在 audio 阶段失败，报错示例：

```text
synthesized audio is too short (1.9s) for a script with 120 CJK characters;
the voice 'af-ZA-AdriNeural' likely does not match the script language —
pick a voice that matches the script language
```

边界说明：守卫在任务层，覆盖全部 TTS provider；阈值常量 `_AUDIO_SANITY_GUARD_MIN_CJK_CHARS = 50`、`_AUDIO_SANITY_GUARD_MIN_SECONDS = 5.0`；用取整前的实测秒数比较（避免 `ceil` 把 4.1s 抬到 5 漏判）；用户自备的自定义音频不参与守卫；短脚本（≤50 CJK 字符）配短音频属合法结果，不拦截。

测试：`test/services/test_azure_tts_no_audio.py`、`test/services/test_audio_sanity_guard.py`。

---

## 3. 如何避免

1. **按脚本语言选声音**。中文脚本选 `zh-CN-*`（如 `zh-CN-XiaoxiaoNeural`）；跨语言脚本可用 `zh-CN-XiaoxiaoMultilingualNeural-V2`。
2. **WebUI 声音列表 zh 系已置顶**：`get_all_azure_voices` 分组排序后 15 个 `zh-*` 声音排在最前，字母序的冷门语言（af/aráb…）退居其后。
3. **切换语言时重新选声音**：改 `video_language` 不会自动迁移 `voice_name`，已保存的声音会一直沿用。
4. API 调用方：`voice_name` 传区域前缀与脚本一致的声音 ID（性别后缀 `-Female/-Male` 会被 `parse_voice_name` 剥离）。

---

## 4. 排查速查

| 症状 | 结论 |
|---|---|
| 日志出现 `NoAudioReceived`，重试恰 1 次后失败 | 声音语言不匹配（确定性），换声音，不要查网络 |
| 任务 audio 阶段失败，报错含 "too short ... CJK characters" | 声音只朗读了脚本中的非中文片段，换匹配语言的声音 |
| TTS 瞬时错误重试 3 次后失败 | 连接/超时类问题，按 `edge_tts_timeout` 与网络排查 |
