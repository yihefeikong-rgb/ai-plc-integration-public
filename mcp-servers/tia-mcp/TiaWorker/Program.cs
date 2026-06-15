using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using Siemens.Engineering;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;
using Siemens.Engineering.SW.ExternalSources;
using Siemens.Engineering.Compiler;
using Siemens.Engineering.Download;
using Siemens.Engineering.Connection;

namespace TiaWorker
{
    class Program
    {
        static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

        // 调试模式开关（环境变量 TIAWORKER_DEBUG=1 启用）
        private static bool IsDebugEnabled =>
            string.Equals(Environment.GetEnvironmentVariable("TIAWORKER_DEBUG"), "1", StringComparison.OrdinalIgnoreCase);

        // TIA Portal V21 Openness DLL 路径
        // Private=False 编译（避免 CopyLocal 检查），运行时通过 AssemblyResolve 加载
        static readonly string[] _tiaDllPaths = new[]
        {
            @"D:\TIA BEN TI\Portal V21\PublicAPI\V21\net48",
            @"D:\TIA BEN TI\Portal V21\Bin\PublicAPI",
        }; 

        static Program()
        {
            AppDomain.CurrentDomain.AssemblyResolve += (sender, args) =>
            {
                var name = new AssemblyName(args.Name).Name;
                if (!name.StartsWith("Siemens.Engineering", StringComparison.OrdinalIgnoreCase))
                    return null;

                foreach (var dir in _tiaDllPaths)
                {
                    var dllPath = Path.Combine(dir, name + ".dll");
                    if (File.Exists(dllPath))
                        return Assembly.LoadFrom(dllPath);
                }
                return null;
            };
        }

        static int Main(string[] args)
        {
            if (args.Length < 2)
            {
                Console.WriteLine(JsonError("Usage: TiaWorker.exe <command> <jsonFile>"));
                return 1;
            }

            var command = args[0];
            var jsonFile = args[1];

            if (!File.Exists(jsonFile))
            {
                Console.WriteLine(JsonError($"File not found: {jsonFile}"));
                return 1;
            }

            try
            {
                var json = File.ReadAllText(jsonFile);
                switch (command)
                {
                    case "import-scl":
                        return ImportScl(json);
                    case "create-lad":
                        Console.WriteLine(LadderBuilder.Execute(json));
                        return 0;
                    case "compile":
                        return Compile(json);
                    case "download":
                        return Download(json);
                    case "download-gui":
                        return DownloadGui(json);
                    case "list-devices":
                        return ListDevices(json);
                    case "create-block":
                        return CreateBlock(json);
                    case "export-block":
                        return ExportBlock(json);
                    case "import-block":
                        return ImportBlock(json);
                    default:
                        Console.WriteLine(JsonError($"Unknown command: {command}"));
                        return 1;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(JsonError(ex.ToString()));
                return 1;
            }
        }

        static int ImportScl(string json)
        {
            var input = Json.Deserialize<ImportSclInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) ||
                string.IsNullOrEmpty(input?.SclFilePath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or SclFilePath"));
                return 1;
            }

            var sclFile = new FileInfo(input.SclFilePath);
            if (!sclFile.Exists)
            {
                Console.WriteLine(JsonError($"SCL file not found: {input.SclFilePath}"));
                return 1;
            }

            using (var tia = new TiaPortal(TiaPortalMode.WithUserInterface))
            {
                var projectPath = new FileInfo(input.ProjectPath);
                if (!projectPath.Exists)
                {
                    Console.WriteLine(JsonError($"Project not found: {input.ProjectPath}"));
                    return 1;
                }

                var project = tia.Projects.Open(projectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found in project"));
                    return 1;
                }

                // Import external source file
                var extGroup = plcSoftware.ExternalSourceGroup;
                var extSources = extGroup.ExternalSources;
                var extSource = extSources.CreateFromFile(sclFile.Name, sclFile.FullName);

                // Generate blocks from source
                var generated = extSource.GenerateBlocksFromSource(GenerateBlockOption.None);

                project.Save();

                Console.WriteLine(JsonOk(new
                {
                    fileName = sclFile.Name,
                    generated = generated.Count,
                    blocks = generated.OfType<PlcBlock>().Select(b => b.Name).ToArray()
                }));
                return 0;
            }
        }

        static int Compile(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = new TiaPortal(TiaPortalMode.WithUserInterface))
            {
                var project = tia.Projects.Open(new FileInfo(input.ProjectPath));
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var compiler = plcSoftware.GetService<ICompilable>();
                var result = compiler.Compile();

                project.Save();

                Console.WriteLine(JsonOk(new
                {
                    success = result.State == CompilerResultState.Success,
                    errors = result.ErrorCount,
                    warnings = result.WarningCount
                }));
                return result.State == CompilerResultState.Success ? 0 : 1;
            }
        }

        static int Download(string json)
        {
            var input = Json.Deserialize<DownloadInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            var interfaceName = input?.InterfaceName ?? "PN/IE";
            var targetIp = input?.TargetIp ?? "";

            // WithUserInterface 需要已有 TIA Portal 进程，这里用 WithoutUserInterface
            // 如果下载过程需要 GUI 确认，会抛出异常并触发 fallback
            using (var tia = new TiaPortal(TiaPortalMode.WithoutUserInterface))
            {
                var project = tia.Projects.Open(new FileInfo(input.ProjectPath));
                var device = FindDevice(project, input?.DeviceName);

                if (device == null)
                {
                    Console.WriteLine(JsonError("Device not found"));
                    return 1;
                }

                // 1. 查找可下载的 DeviceItem（CPU）
                var downloadItem = FindDownloadableItem(device);
                if (downloadItem == null)
                {
                    Console.WriteLine(JsonOk(new
                    {
                        note = "auto",
                        message = "未找到可自动下载的设备接口。请在 TIA Portal GUI 中手动下载。"
                    }));
                    return 0;
                }

                var downloadProvider = downloadItem.GetService<DownloadProvider>();
                if (downloadProvider == null)
                {
                    Console.WriteLine(JsonOk(new
                    {
                        note = "auto",
                        message = "DownloadProvider 不可用。请在 TIA Portal GUI 中手动下载。"
                    }));
                    return 0;
                }

                // 2. 配置下载连接
                try
                {
                    var connConfig = downloadProvider.Configuration;
                    var mode = connConfig.Modes.Find(interfaceName);
                    if (mode == null)
                    {
                        Console.WriteLine(JsonOk(new
                        {
                            note = "auto",
                            message = $"未找到通信模式 '{interfaceName}'。请在 TIA Portal GUI 中手动下载。"
                        }));
                        return 0;
                    }

                    // 调试：枚举所有接口
                    if (IsDebugEnabled) Console.Error.WriteLine($"[TiaWorker] 可用模式: {string.Join(", ", connConfig.Modes.Select(m => m.Name))}");
                    foreach (var iface in mode.PcInterfaces)
                    {
                        if (IsDebugEnabled) Console.Error.WriteLine($"[TiaWorker]   接口: {iface.Name}");
                    }

                    // 优先选择 PLCSIM Softbus 接口（不含 "Ethernet"/"Virtual"）
                    ConfigurationPcInterface pcInterface = null;
                    foreach (var iface in mode.PcInterfaces)
                    {
                        var name = iface.Name ?? "";
                        if (name.IndexOf("PLCSIM", StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            // Softbus 模式接口名不含 "Ethernet"/"Virtual"
                            if (name.IndexOf("Ethernet", StringComparison.OrdinalIgnoreCase) < 0 &&
                                name.IndexOf("Virtual", StringComparison.OrdinalIgnoreCase) < 0)
                            {
                                pcInterface = iface;
                                break;
                            }
                            // 记住第一个候选（可能在列表前面）
                            if (pcInterface == null)
                                pcInterface = iface;
                        }
                    }
                    pcInterface ??= mode.PcInterfaces.Count > 0 ? mode.PcInterfaces[0] : null;

                    if (pcInterface == null)
                    {
                        Console.WriteLine(JsonOk(new
                        {
                            note = "auto",
                            message = "未找到可用 PC 接口。请在 TIA Portal GUI 中手动下载。"
                        }));
                        return 0;
                    }

                    // 找目标设备配置
                    IConfiguration targetConfig = null;
                    if (!string.IsNullOrEmpty(targetIp))
                    {
                        // 先找子网中的地址
                        foreach (var subnet in pcInterface.Subnets)
                        {
                            try
                            {
                                targetConfig = subnet.Addresses.Find(targetIp);
                                if (targetConfig != null) break;
                            }
                            catch { }
                        }
                    }
                    // 取第一个目标接口
                    if (targetConfig == null && pcInterface.TargetInterfaces.Count > 0)
                    {
                        targetConfig = pcInterface.TargetInterfaces[0];
                    }

                    if (targetConfig == null)
                    {
                        Console.WriteLine(JsonOk(new
                        {
                            note = "auto",
                            message = "未找到目标 PLC。请在 TIA Portal GUI 中手动下载。"
                        }));
                        return 0;
                    }

                    // 3. 设置下载目标为 PLCSIM Advanced（V21 关键！否则默认找真实硬件）
                    if (IsDebugEnabled) Console.Error.WriteLine($"[TiaWorker] 设置下载目标为 PLCSIM Advanced...");

                    DownloadConfigurationDelegate preDelegate = (cfg) =>
                    {
                        try
                        {
                            // 设置 TargetForSoftware → PlcSimulationAdvanced
                            var targetForSoftware = cfg.GetType().GetProperty("TargetForSoftware");
                            if (targetForSoftware != null)
                            {
                                var targetObj = targetForSoftware.GetValue(cfg);
                                if (targetObj != null)
                                {
                                    var currentSelProp = targetObj.GetType().GetProperty("CurrentSelection");
                                    if (currentSelProp != null)
                                    {
                                        var selectionsType = currentSelProp.PropertyType;
                                        var plcSimAdv = Enum.Parse(selectionsType, "PlcSimulationAdvanced");
                                        currentSelProp.SetValue(targetObj, plcSimAdv);
                                        if (IsDebugEnabled) Console.Error.WriteLine("[TiaWorker] ✅ TargetForSoftware = PlcSimulationAdvanced");
                                    }
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            if (IsDebugEnabled) Console.Error.WriteLine($"[TiaWorker] ⚠ 设置 TargetForSoftware 失败: {ex.Message}");
                        }
                    };

                    var result = downloadProvider.Download(
                        targetConfig,
                        preDelegate,
                        new DownloadConfigurationDelegate(cfg => { }),
                        DownloadOptions.Software);

                    project.Save();

                    var success = result.State == DownloadResultState.Success;

                    Console.WriteLine(JsonOk(new
                    {
                        success,
                        state = result.State.ToString(),
                        errors = result.ErrorCount,
                        message = success
                            ? "已成功下载到 PLCSIM"
                            : $"下载状态: {result.State}，错误: {result.ErrorCount}"
                    }));
                    return success ? 0 : 1;
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonOk(new
                    {
                        note = "auto",
                        message = $"API 下载尝试需 GUI 确认: {ex.Message}",
                        fallback = "请查看 TIA Portal GUI 窗口，确认下载对话框。",
                        detail = ex.ToString()
                    }));
                    return 0;
                }
            }
        }

        static int DownloadGui(string json)
        {
            var input = Json.Deserialize<DownloadInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            var interfaceName = input?.InterfaceName ?? "PN/IE";
            var targetIp = input?.TargetIp ?? "";

            // GUI 模式：附加到已运行的 TIA Portal GUI
            // WithUserInterface 不会启动新实例，而是附加到现有 GUI 进程
            try
            {
                using (var tia = new TiaPortal(TiaPortalMode.WithUserInterface))
                {
                    var project = tia.Projects.Open(new FileInfo(input.ProjectPath));
                    var device = FindDevice(project, input?.DeviceName);

                    if (device == null)
                    {
                        Console.WriteLine(JsonError("Device not found"));
                        return 1;
                    }

                    var downloadItem = FindDownloadableItem(device);
                    if (downloadItem == null)
                    {
                        Console.WriteLine(JsonOk(new { note = "no_device", message = "未找到可下载的设备接口" }));
                        return 0;
                    }

                    var downloadProvider = downloadItem.GetService<DownloadProvider>();
                    if (downloadProvider == null)
                    {
                        Console.WriteLine(JsonOk(new { note = "no_provider", message = "DownloadProvider 不可用" }));
                        return 0;
                    }

                    // 配置下载连接
                    var connConfig = downloadProvider.Configuration;
                    var mode = connConfig.Modes.Find(interfaceName);
                    if (mode == null)
                    {
                        Console.WriteLine(JsonOk(new { note = "no_mode", message = $"未找到通信模式 '{interfaceName}'" }));
                        return 0;
                    }

                    // 优先选择 PLCSIM Softbus 接口
                    ConfigurationPcInterface pcInterface = null;
                    foreach (var iface in mode.PcInterfaces)
                    {
                        var name = iface.Name ?? "";
                        if (name.IndexOf("PLCSIM", StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            if (name.IndexOf("Ethernet", StringComparison.OrdinalIgnoreCase) < 0 &&
                                name.IndexOf("Virtual", StringComparison.OrdinalIgnoreCase) < 0)
                            {
                                pcInterface = iface;
                                break;
                            }
                            pcInterface ??= iface;
                        }
                    }
                    pcInterface ??= mode.PcInterfaces.Count > 0 ? mode.PcInterfaces[0] : null;

                    if (pcInterface == null)
                    {
                        Console.WriteLine(JsonOk(new { note = "no_interface", message = "未找到可用 PC 接口" }));
                        return 0;
                    }

                    // 找目标 PLC 地址
                    IConfiguration targetConfig = null;
                    if (!string.IsNullOrEmpty(targetIp))
                    {
                        foreach (var subnet in pcInterface.Subnets)
                        {
                            try { targetConfig = subnet.Addresses.Find(targetIp); if (targetConfig != null) break; }
                            catch { }
                        }
                    }
                    targetConfig ??= (pcInterface.TargetInterfaces.Count > 0 ? pcInterface.TargetInterfaces[0] : null);

                    if (targetConfig == null)
                    {
                        Console.WriteLine(JsonOk(new { note = "no_target", message = "未找到目标 PLC" }));
                        return 0;
                    }

                    // 设置下载目标为 PLCSIM Advanced
                    try
                    {
                        var configType = downloadProvider.Configuration.GetType();
                        var targetProp = configType.GetProperty("TargetForSoftware");
                        if (targetProp != null)
                        {
                            var targetObj = targetProp.GetValue(downloadProvider.Configuration, null);
                            if (targetObj != null)
                            {
                                var selProp = targetObj.GetType().GetProperty("CurrentSelection");
                                if (selProp != null)
                                {
                                    var enumType = selProp.PropertyType;
                                    try
                                    {
                                        var plcSimAdv = Enum.Parse(enumType, "PlcSimulationAdvanced");
                                        selProp.SetValue(targetObj, plcSimAdv, null);
                                    }
                                    catch
                                    {
                                        // 枚举名可能不同，尝试索引方式
                                        try
                                        {
                                            var values = enumType.GetEnumValues();
                                            if (values.Length > 1)
                                                selProp.SetValue(targetObj, values.GetValue(1), null);
                                        }
                                        catch { }
                                    }
                                }
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        if (IsDebugEnabled) Console.Error.WriteLine($"[TiaWorker] ⚠ 设置 TargetForSoftware 失败: {ex.Message}");
                    }

                    // 执行下载
                    try
                    {
                        DownloadConfigurationDelegate preDelegate = (cfg) =>
                        {
                            try
                            {
                                var p = cfg.GetType().GetProperty("TargetForSoftware");
                                if (p != null)
                                {
                                    var obj = p.GetValue(cfg, null);
                                    if (obj != null)
                                    {
                                        var sel = obj.GetType().GetProperty("CurrentSelection");
                                        if (sel != null)
                                        {
                                            try { sel.SetValue(obj, Enum.Parse(sel.PropertyType, "PlcSimulationAdvanced"), null); }
                                            catch { }
                                        }
                                    }
                                }
                            }
                            catch { }
                        };

                        var result = downloadProvider.Download(
                            targetConfig,
                            preDelegate,
                            new DownloadConfigurationDelegate(cfg => { }),
                            DownloadOptions.Software);

                        project.Save();

                        var success = result.State == DownloadResultState.Success;
                        Console.WriteLine(JsonOk(new
                        {
                            success,
                            state = result.State.ToString(),
                            errors = result.ErrorCount,
                            message = success
                                ? "✅ 已成功下载到 PLCSIM (GUI 模式)"
                                : $"下载状态: {result.State}，错误: {result.ErrorCount}"
                        }));
                        return success ? 0 : 1;
                    }
                    catch (Exception ex)
                    {
                        // GUI 模式下下载失败（可能是对话框需要确认）
                        // 返回 0 + note=gui_confirm 触发下一个降级策略
                        Console.WriteLine(JsonOk(new
                        {
                            note = "gui_confirm",
                            message = $"下载需要 GUI 确认: {ex.Message}",
                            fallback = "请检查 TIA Portal GUI 窗口，确认下载对话框。"
                        }));
                        return 0;
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(JsonError($"附加 TIA Portal GUI 失败: {ex.Message}"));
                return 1;
            }
        }

        /// <summary>
        /// 递归查找支持 DownloadProvider 的 DeviceItem。
        /// 通常为 CPU 模块（device.DeviceItems[0].DeviceItems[0]）。
        /// </summary>
        static DeviceItem FindDownloadableItem(Device device)
        {
            foreach (var topItem in device.DeviceItems)
            {
                var found = FindDownloadableItemRecursive(topItem, 0);
                if (found != null) return found;
            }
            return null;
        }

        static DeviceItem FindDownloadableItemRecursive(DeviceItem item, int depth)
        {
            if (depth > 10) return null;
            try
            {
                var dp = item.GetService<DownloadProvider>();
                if (dp != null) return item;
            }
            catch { }
            foreach (var child in item.DeviceItems)
            {
                var found = FindDownloadableItemRecursive(child, depth + 1);
                if (found != null) return found;
            }
            return null;
        }

        static int ListDevices(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = new TiaPortal(TiaPortalMode.WithUserInterface))
            {
                var project = tia.Projects.Open(new FileInfo(input.ProjectPath));
                var devices = project.Devices
                    .Select(d => new { name = d.Name, type = d.TypeIdentifier })
                    .ToArray();

                Console.WriteLine(JsonOk(new { devices }));
                return 0;
            }
        }

        static int CreateBlock(string json)
        {
            var input = Json.Deserialize<CreateBlockInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.BlockName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or BlockName"));
                return 1;
            }

            using (var tia = new TiaPortal(TiaPortalMode.WithUserInterface))
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found in project"));
                    return 1;
                }

                var blocks = plcSoftware.BlockGroup.Blocks;
                var inputBlockType = (input.BlockType ?? "FB").ToUpperInvariant();
                var inputLanguage = (input.Language ?? "LAD").ToUpperInvariant();

                PlcBlock block;

                // 策略 1：V21 CreateFB(name, isAutoNumbered, number, ProgrammingLanguage)
                var createFbMethod = blocks.GetType().GetMethod("CreateFB");
                if (createFbMethod != null && inputBlockType == "FB")
                {
                    var langParamType = createFbMethod.GetParameters()[3].ParameterType;
                    var langValue = ResolveEnumByName(langParamType, inputLanguage);
                    if (langValue == null)
                    {
                        Console.WriteLine(JsonError($"Invalid Language: {inputLanguage}. Supported: LAD, FBD, SCL, STL"));
                        return 1;
                    }

                    var autoNum = input.BlockNumber <= 0;
                    var number = input.BlockNumber > 0 ? input.BlockNumber : 0;

                    if (IsDebugEnabled)
                        Console.Error.WriteLine($"[TiaWorker] V21 CreateFB: name={input.BlockName}, auto={autoNum}, num={number}, lang={inputLanguage}");

                    block = (PlcBlock)createFbMethod.Invoke(blocks, new object[] { input.BlockName, autoNum, number, langValue });
                }
                // 策略 2：V18 Create(name, PlcBlockType, PlcProgrammingLanguage)
                else
                {
                    var createMethod = blocks.GetType().GetMethods()
                        .FirstOrDefault(m => m.Name == "Create" && m.GetParameters().Length >= 3);
                    if (createMethod == null)
                    {
                        Console.WriteLine(JsonError($"No Create/CreateFB method found. BlockType '{inputBlockType}' may not be supported in this TIA version."));
                        return 1;
                    }

                    var parms = createMethod.GetParameters();
                    var blockTypeValue = ResolveEnumByName(parms[1].ParameterType, inputBlockType == "FB" ? "FunctionBlock" : inputBlockType == "FC" ? "Function" : inputBlockType == "DB" ? "GlobalDB" : "OrganizationBlock");
                    var langValue = ResolveEnumByName(parms[2].ParameterType, inputLanguage);

                    if (blockTypeValue == null || langValue == null)
                    {
                        Console.WriteLine(JsonError($"Invalid BlockType/Language: {inputBlockType}/{inputLanguage}"));
                        return 1;
                    }

                    block = (PlcBlock)createMethod.Invoke(blocks, new object[] { input.BlockName, blockTypeValue, langValue });
                }

                project.Save();

                Console.WriteLine(JsonOk(new
                {
                    blockName = block.Name,
                    number = block.Number
                }));
                return 0;
            }
        }

        /// <summary>
        /// 通过枚举名称在 Type 上做 Enum.Parse（反射方式，兼容 V18/V21）
        /// </summary>
        static object ResolveEnumByName(Type enumType, string name)
        {
            try { return Enum.Parse(enumType, name, true); }
            catch { return null; }
        }

        /// <summary>
        /// 获取已打开的项目，或打开指定路径的项目。
        /// 解决 V21 中 Portal GUI 已打开项目时 Open 会报错的问题。
        /// </summary>
        static Project GetOrOpenProject(TiaPortal tia, string projectPath)
        {
            var targetPath = new FileInfo(projectPath).FullName;

            // 先检查已打开的项目
            foreach (Project proj in tia.Projects)
            {
                try
                {
                    if (proj.Path != null && proj.Path.FullName.Equals(targetPath, StringComparison.OrdinalIgnoreCase))
                    {
                        if (IsDebugEnabled)
                            Console.Error.WriteLine($"[TiaWorker] Using already-open project: {proj.Path.FullName}");
                        return proj;
                    }
                }
                catch { }
            }

            // 没找到，尝试打开
            if (IsDebugEnabled)
                Console.Error.WriteLine($"[TiaWorker] Opening project: {targetPath}");
            return tia.Projects.Open(new FileInfo(projectPath));
        }

        static int ExportBlock(string json)
        {
            var input = Json.Deserialize<ExportBlockInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.BlockName) || string.IsNullOrEmpty(input?.OutputPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath, BlockName, or OutputPath"));
                return 1;
            }

            using (var tia = new TiaPortal(TiaPortalMode.WithUserInterface))
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found in project"));
                    return 1;
                }

                PlcBlock block = null;
                try { block = plcSoftware.BlockGroup.Blocks.Find(input.BlockName); }
                catch { }
                if (block == null)
                {
                    Console.WriteLine(JsonError($"Block '{input.BlockName}' not found"));
                    return 1;
                }

                // 通过 IConvertible 导出 XML（反射避免编译时版本依赖）
                var svc = CallReflectedService(block, "Siemens.Engineering.SW.Blocks.IConvertible");
                if (svc == null)
                {
                    Console.WriteLine(JsonError("Export not supported (IConvertible not available on this block)"));
                    return 1;
                }

                var svcType = svc.GetType();
                var exportMethod = svcType.GetMethod("Export");
                if (exportMethod == null)
                {
                    Console.WriteLine(JsonError("Export method not found on IConvertible interface"));
                    return 1;
                }

                // ExportOptions.WithDefaults = 1
                exportMethod.Invoke(svc, new object[] { new FileInfo(input.OutputPath), 1 });

                project.Save();

                Console.WriteLine(JsonOk(new
                {
                    blockName = input.BlockName,
                    outputPath = input.OutputPath
                }));
                return 0;
            }
        }

        static int ImportBlock(string json)
        {
            var input = Json.Deserialize<ImportBlockInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.FilePath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or FilePath"));
                return 1;
            }

            var xmlFile = new FileInfo(input.FilePath);
            if (!xmlFile.Exists)
            {
                Console.WriteLine(JsonError($"XML file not found: {input.FilePath}"));
                return 1;
            }

            using (var tia = new TiaPortal(TiaPortalMode.WithUserInterface))
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found in project"));
                    return 1;
                }

                var blocks = plcSoftware.BlockGroup.Blocks;

                // 查找 Import(FileInfo, ImportOptions) 方法
                var importMethod = blocks.GetType().GetMethods()
                    .FirstOrDefault(m => m.Name == "Import" && m.GetParameters().Length == 2);

                if (importMethod == null)
                {
                    Console.WriteLine(JsonError("Import method not found (TIA API version mismatch)"));
                    return 1;
                }

                // 从 MethodInfo 获取 ImportOptions 枚举类型并解析
                var optionsParamType = importMethod.GetParameters()[1].ParameterType;
                var optionsValue = ResolveEnumByName(optionsParamType, input.Override ? "Override" : "None");
                if (optionsValue == null)
                {
                    optionsValue = input.Override ? 1 : 0;
                }

                var result = importMethod.Invoke(blocks, new object[] { xmlFile, optionsValue });

                project.Save();

                // 提取导入的块名
                string[] blockNames = null;
                if (result is System.Collections.IEnumerable enumerable)
                {
                    blockNames = enumerable.OfType<PlcBlock>().Select(b => b.Name).ToArray();
                }

                Console.WriteLine(JsonOk(new
                {
                    filePath = input.FilePath,
                    @override = input.Override,
                    blocks = blockNames ?? new[] { "imported" }
                }));
                return 0;
            }
        }

        /// <summary>
        /// 反射调用 GetService&lt;T&gt;，避免编译时对特定 TIA API 版本的强依赖
        /// </summary>
        static object CallReflectedService(object target, string interfaceFullName)
        {
            var iface = target.GetType().Assembly.GetType(interfaceFullName);
            if (iface == null) return null;

            var getServiceGeneric = target.GetType().GetMethod("GetService`1");
            if (getServiceGeneric == null) return null;

            var getServiceTyped = getServiceGeneric.MakeGenericMethod(iface);
            return getServiceTyped.Invoke(target, null);
        }

        internal static PlcSoftware GetPlcSoftware(Project project)
        {
            foreach (var device in project.Devices)
            {
                foreach (var deviceItem in device.DeviceItems)
                {
                    try
                    {
                        var container = deviceItem.GetService<SoftwareContainer>();
                        if (container?.Software is PlcSoftware plc)
                            return plc;
                    }
                    catch { }
                }
            }
            return null;
        }

        static Device FindDevice(Project project, string name)
        {
            if (string.IsNullOrEmpty(name))
                return project.Devices.FirstOrDefault();
            return project.Devices.FirstOrDefault(d =>
                d.Name.Equals(name, StringComparison.OrdinalIgnoreCase));
        }

        static string JsonOk(object data) =>
            Json.Serialize(new { status = "ok", data });

        static string JsonError(string msg) =>
            Json.Serialize(new { status = "error", error = msg });
    }

    class ProjectInput
    {
        public string ProjectPath { get; set; }
    }

    class ImportSclInput : ProjectInput
    {
        public string SclFilePath { get; set; }
    }

    class DownloadInput : ProjectInput
    {
        public string DeviceName { get; set; }
        public string InterfaceName { get; set; }
        public string TargetIp { get; set; }
        public int TimeoutSec { get; set; }
    }

    class CreateBlockInput : ProjectInput
    {
        public string BlockName { get; set; }
        public int BlockNumber { get; set; }
        public string BlockType { get; set; }
        public string Language { get; set; }
    }

    class ExportBlockInput : ProjectInput
    {
        public string BlockName { get; set; }
        public string OutputPath { get; set; }
    }

    class ImportBlockInput : ProjectInput
    {
        public string FilePath { get; set; }
        public bool Override { get; set; }
    }
}
