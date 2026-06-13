"""
快速生成自定义 LAD 块：改 description 就行
"""
import json, re, subprocess, tempfile, os, sys
from config_loader import cfg

API_KEY = cfg.deepseek.api_key
if not API_KEY:
    print("❌ 请设置环境变量 DEEPSEEK_API_KEY（或在 .env 文件中定义）")
    sys.exit(1)

# ═════ 改这里就行 ═════
DESCRIPTION = "水泵自动控制，高液位启动，低液位停止，带手动/自动切换和过载保护"
BLOCK_NAME = "PumpControl"
# ════════════════════

prompt = f"""你是一个西门子 PLC 梯形图 (LAD) 专家。请根据以下描述生成 LadderSpec JSON。

## 输出格式
```json
{{
  "blockName": "英文驼峰命名",
  "blockNumber": 500,
  "interface": {{
    "inputs": [{{"name": "iXxx", "type": "Bool", "comment": "中文注释", "address": "%I0.0"}}],
    "outputs": [{{"name": "oXxx", "type": "Bool", "comment": "中文注释", "address": "%Q0.0"}}],
    "local": [{{"name": "mXxx", "type": "Bool", "comment": "中文注释"}}]
  }},
  "networks": [
    {{
      "title": "网络标题",
      "comment": "逻辑说明",
      "elements": [
        {{"type": "normally_open|normally_closed|coil|coil_set|coil_reset", "operand": "变量名"}}
      ]
    }}
  ]
}}
```

## 地址分配规则
- inputs 的 address 从 %I0.0 开始递增（%I0.0, %I0.1, %I0.2...）
- outputs 的 address 从 %Q0.0 开始递增（%Q0.0, %Q0.1, %Q0.2...）
- local/memory 变量不需要 address

## 安全规则
- 【不要用 parallelElements】CartGen 不支持并联分支
- 自保持用 Set/Reset 模式：启动 Set，停止 Reset
- 所有输出必须有急停互锁
- 正转/反转必须互锁

## 变量命名
- 输入: iXxx, 输出: oXxx, 本地: mXxx

## 用户描述
{description}"""

print(f"生成: {BLOCK_NAME}")
print(f"描述: {DESCRIPTION}")
print()

# 1. 调 DeepSeek
import requests
resp = requests.post(
    cfg.deepseek.api_url,
    headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
    json={'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}],
          'temperature': 0.3, 'max_tokens': 4000},
    timeout=60
)
content = resp.json()['choices'][0]['message']['content']

# 2. 解析 JSON
m = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
raw = (m.group(1) if m else content).strip()
spec = json.loads(raw)
spec['blockName'] = BLOCK_NAME
print(f"✅ DeepSeek: {len(spec['networks'])} 个网络")

# 3. SVG 预览
sys.path.insert(0, r'mcp-servers/tia-mcp')
from ladder_renderer import render_svg_preview
svg = render_svg_preview(spec)
svg_path = os.path.join(tempfile.gettempdir(), f"{BLOCK_NAME}.svg")
with open(svg_path, 'w') as f:
    f.write(svg)
print(f"✅ SVG 预览: {svg_path}")

# 4. CartGen 生成 XML
tmp = os.path.join(tempfile.gettempdir(), f'lad_{BLOCK_NAME}.json')
with open(tmp, 'w') as f:
    json.dump(spec, f, ensure_ascii=False, indent=2)

xml_out = os.path.join(cfg.tia.output_dir, f'{BLOCK_NAME}.xml')
dll = cfg.cartgen.dll_path
r = subprocess.run(['dotnet', 'exec', dll, tmp, xml_out], capture_output=True, timeout=60)
if r.returncode != 0:
    print(f"❌ CartGen 失败: {r.stderr.decode()[:300]}")
    sys.exit(1)

print(f"✅ XML: {xml_out}")

# 5. 清洗 + 导入 TIA
with open(xml_out, 'r', encoding='utf-8') as f:
    xml = f.read()
xml = re.sub(
    r'<MultilingualTextItem[^>]*>\s*<AttributeList>\s*<Culture>[^<]*</Culture>\s*<Text\s*/>\s*</AttributeList>\s*</MultilingualTextItem>\s*',
    '', xml)
with open(xml_out, 'w', encoding='utf-8') as f:
    f.write(xml)

import clr
_tia_dir = cfg.tia.install_dir
clr.AddReference(rf'{_tia_dir}\PublicAPI\V18\Siemens.Engineering.dll')
clr.AddReference(rf'{_tia_dir}\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
from Siemens.Engineering import TiaPortal, TiaPortalMode, ImportOptions
from Siemens.Engineering.SW import SWImportOptions
from Siemens.Engineering.SW.ExternalSources import GenerateBlockOption
from Siemens.Engineering.HW.Features import SoftwareContainer
from Siemens.Engineering.Compiler import ICompilable
from System.IO import FileInfo

tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
try:
    project = tia.Projects.Open(FileInfo(cfg.tia.project_path))
    plc_sw = None
    for device in project.Devices:
        for item in device.DeviceItems:
            c = item.GetService[SoftwareContainer]()
            if c and c.Software and 'PlcSoftware' in c.Software.GetType().FullName:
                plc_sw = c.Software; break
        if plc_sw: break

    # 5a. 导入原 FB
    plc_sw.BlockGroup.Blocks.Import(FileInfo(xml_out), ImportOptions.Override, SWImportOptions(2))
    print("✅ FB 导入成功")

    # 5b. 生成并导入 IO 映射 FB
    from gen_io_map import generate_io_map
    io_map_scl = generate_io_map(tmp)
    io_map_name = f"IO_Map_{BLOCK_NAME}"
    scl_path = os.path.join(os.path.dirname(xml_out), 'scl', f"{io_map_name}.scl")
    os.makedirs(os.path.dirname(scl_path), exist_ok=True)
    with open(scl_path, 'w', encoding='utf-8-sig') as f:
        f.write(io_map_scl)
    print(f"✅ IO 映射 SCL: {scl_path}")

    try:
        ext_group = plc_sw.ExternalSourceGroup
        if ext_group is not None:
            ext_source = ext_group.ExternalSources.CreateFromFile(
                os.path.basename(scl_path), scl_path)
            gen_blocks = ext_source.GenerateBlocksFromSource(getattr(GenerateBlockOption, 'None'))
            print(f"✅ IO 映射导入: 生成了 {gen_blocks.Count} 个块")
        else:
            print(f"⚠ ExternalSourceGroup 不可用，手动导入: {scl_path}")
    except Exception as e:
        print(f"⚠ IO 映射导入失败: {e}")
        print(f"   手动导入: {scl_path}")

    compiler = plc_sw.GetService[ICompilable]()
    cr = compiler.Compile()
    print(f"✅ 编译: State={cr.State}, Errors={cr.ErrorCount}, Warnings={cr.WarningCount}")
    project.Save()
finally:
    tia.Dispose()

print()
print("=" * 50)
print(f"🎉 {BLOCK_NAME} 已创建！")
print(f"   SVG: {svg_path}")
print(f"   TIA Portal 中查看: {BLOCK_NAME} (LAD)")
print("=" * 50)
