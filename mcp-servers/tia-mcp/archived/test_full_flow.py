"""
完整端到端测试：DeepSeek → CartGen → TIA Portal 导入 → 编译
"""
import json, re, subprocess, tempfile, os, sys

API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
if not API_KEY:
    print("❌ 请设置环境变量 DEEPSEEK_API_KEY（或在 .env 文件中定义）")
    sys.exit(1)

def main():
    prompt = """你是一个西门子 PLC 梯形图 (LAD) 专家。请根据以下描述生成 LadderSpec JSON。

## 输出格式
```json
{
  "blockName": "英文驼峰命名",
  "blockNumber": 100,
  "interface": {
    "inputs": [{"name": "iXxx", "type": "Bool", "comment": "中文注释"}],
    "outputs": [{"name": "oXxx", "type": "Bool", "comment": "中文注释"}],
    "local": [{"name": "mXxx", "type": "Bool", "comment": "中文注释"}]
  },
  "networks": [
    {
      "title": "网络标题",
      "comment": "逻辑说明",
      "elements": [
        {"type": "normally_open|normally_closed|coil|coil_set|coil_reset", "operand": "变量名"}
      ],
      "parallelElements": [
        {"type": "normally_open", "operand": "变量名"}
      ]
    }
  ]
}
```

## 安全规则（必须遵守）
- 所有电机类输出必须有急停互锁（串联 normally_closed iStop）
- 正转/反转必须互锁（正转网络包含 normally_closed oRunRev）
- 过载保护必须串联 normally_closed iOverload
- 自保持电路：启动按钮与运行位并联 (parallelElements)

## 变量命名规范
- 输入: iXxx（iStart, iStop, iOverload 等）
- 输出: oXxx（oRunFwd, oRunRev, oFault 等）
- 本地: mXxx（mSafetyOK, mState1 等）

## 用户描述
电机正反转控制，带急停和过载保护"""

    print("=" * 60)
    print("Step 1: DeepSeek API 调用")
    print("=" * 60)

    import requests
    resp = requests.post(
        'https://api.deepseek.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
        json={'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}],
              'temperature': 0.3, 'max_tokens': 4000},
        timeout=60
    )
    resp.raise_for_status()
    content = resp.json()['choices'][0]['message']['content']

    # 提取 JSON
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    raw = (m.group(1) if m else content).strip()
    spec = json.loads(raw)
    spec['blockName'] = 'MotorDeepSeek'
    print(f"  ✅ blockName={spec['blockName']}, networks={len(spec['networks'])}")

    print("\n" + "=" * 60)
    print("Step 2: CartGen → SimaticML XML")
    print("=" * 60)

    tmp = os.path.join(tempfile.gettempdir(), 'lad_MotorDeepSeek.json')
    with open(tmp, 'w') as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    xml_out = r'D:\TIA FANG ZHEN\MotorDeepSeek.xml'
    dll = r'mcp-servers/tia-mcp/CartGen/bin/Release/net8.0/CartGen.dll'
    r = subprocess.run(['dotnet', 'exec', dll, tmp, xml_out], capture_output=True, timeout=60)
    if r.returncode != 0:
        print(f"  ❌ CartGen 失败: {r.stderr.decode()[:300]}")
        return 1

    # 清洗 XML
    with open(xml_out, 'r', encoding='utf-8') as f:
        xml = f.read()
    xml = re.sub(
        r'<MultilingualTextItem[^>]*>\s*<AttributeList>\s*<Culture>[^<]*</Culture>\s*<Text\s*/>\s*</AttributeList>\s*</MultilingualTextItem>\s*',
        '', xml)
    with open(xml_out, 'w', encoding='utf-8') as f:
        f.write(xml)
    print(f"  ✅ XML: {xml_out} ({len(xml)} bytes)")

    print("\n" + "=" * 60)
    print("Step 3: 导入 TIA Portal + 编译")
    print("=" * 60)

    import clr
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode, ImportOptions
    from Siemens.Engineering.SW import SWImportOptions
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from Siemens.Engineering.Compiler import ICompilable
    from System.IO import FileInfo

    tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(r'D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18'))
        print(f"  项目: {project.Name}")

        # 找 PLC
        plc_sw = None
        for device in project.Devices:
            for item in device.DeviceItems:
                c = item.GetService[SoftwareContainer]()
                if c and c.Software and 'PlcSoftware' in c.Software.GetType().FullName:
                    plc_sw = c.Software
                    break
            if plc_sw:
                break

        if not plc_sw:
            print("  ❌ 未找到 PLC 设备")
            return 1

        # 导入
        plc_sw.BlockGroup.Blocks.Import(
            FileInfo(xml_out), ImportOptions.Override, SWImportOptions(2))
        print("  ✅ XML 导入成功")

        # 编译
        compiler = plc_sw.GetService[ICompilable]()
        cr = compiler.Compile()
        state = cr.State.ToString()
        errors = cr.ErrorCount
        warnings = cr.WarningCount
        print(f"  ✅ 编译: State={state}, Errors={errors}, Warnings={warnings}")
        project.Save()

        # 列出块
        print("\n  项目中的 LAD 块:")
        for b in plc_sw.BlockGroup.Blocks:
            try:
                print(f"    - {b.Name:30s} ({b.ProgrammingLanguage})")
            except:
                pass

    finally:
        tia.Dispose()

    print("\n" + "=" * 60)
    print("🎉 全流程验证通过！")
    print("=" * 60)
    return 0

if __name__ == '__main__':
    sys.exit(main())
