#!/bin/bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H "Content-Type: application/json" \
  -d '{
    "action": "evaluate",
    "args": {
      "code": "const ta = document.querySelector('"'"'textarea'"'"');
ta.value = '"'"'我正在做一个 AI 接入 PLC 的项目（西门子 S7-1500 + TIA Portal + PLCSIM Advanced V5.0）。
目前用 pythonnet 封装了 PLCSIM Advanced 的 .NET API，卡在最后一步：
PLCSIM Advanced 实例是空壳 CPU，需要硬件配置才能 Run()，
但硬件配置必须通过 TIA Portal GUI 首次下载才能写入。
Openness API 的 DownloadProvider 不支持首次下载（西门子官方限制）。

有什么办法绕过？比如：
1. 用 PLCSIM 其他 API 直接加载硬件配置？
2. 能否直接操作 PLCSIM 的磁盘文件来注入配置？
3. 用 OpenPLC 仿真 + S7 通信模拟绕过？
4. 其他可行方案？

请给具体建议，针对 PLCSIM Advanced V5.0。'"'"';
ta.dispatchEvent(new Event('"'"'input'"'"', {bubbles: true}));
'done'"
    },
    "session": "deepseek"
  }'
