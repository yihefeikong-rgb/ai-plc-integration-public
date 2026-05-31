# TIA Portal LAD 扩展 — 编译与使用

## 文件清单

| 文件 | 作用 |
|------|------|
| `TiaWorker/Program.cs` | ✅ 已更新（加了 `create-lad` 命令） |
| `TiaWorker/LadderBuilder.cs` | ✅ 新增（LAD 块生成逻辑，用反射调用 LAD API） |
| `TiaWorker/TiaWorker.csproj` | ✅ 已有（引用 Siemens DLL） |
| `server.py` | ✅ 已更新（新增 `create_ladder_block` MCP 工具） |

## 编译步骤（在你的 Windows 机器上）

```bash
# 1. 确认西门子 DLL 路径正确
#    打开 TiaWorker.csproj，确保这两个路径指向你的 TIA Portal V18：

<Reference Include="Siemens.Engineering">
  <HintPath>D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll</HintPath>
</Reference>

# 2. 编译
cd mcp-servers/tia-mcp/TiaWorker
build.bat

# 如果报 Siemens.Engineering.SW.Blocks.LAD 命名空间找不到，
# 去掉 LadderBuilder.cs 顶部注释，改为：
#   using Siemens.Engineering.SW.Blocks.LAD;
# 并取消 csproj 中 LAD DLL 的注释引用

# 3. 如果编译通过，会在 ../bin/TiaWorker.exe 更新
```

## 测试

编译之后启动 MCP 服务器，然后对我说：

```
create_ladder_block description="电机正反转控制，含急停互锁和过载保护"
```

会得到：
1. AI 分析描述 → 生成 LAD JSON（急停、正转、反转、过载、复位 5 个网络）
2. TiaWorker 接收 JSON → 通过 Openness API 搭梯级
3. TIA Portal V18 中创建一个 LAD 块

## 原理

```
你说"电机正反转，急停互锁"
    ↓
server.py 的 _gen_lad_via_deepseek()
    解析关键词 → 拼 LAD JSON
    ↓
TiaWorker create-lad
    反射调用 Siemens.Engineering 中的 LAD API
    ↓
TIA Portal V18
    创建 LAD 块 + 搭网络 + 编译
```

## 如果编译报错

大概率是因为这台机器没有 TIA Portal V18 的 DLL。
拿到你的 Windows 开发机上跑 `build.bat` 就行。
