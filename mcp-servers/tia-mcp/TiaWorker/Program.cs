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
using Siemens.Engineering.SW.Tags;
using Siemens.Engineering.SW.ExternalSources;
using System.Xml.Linq;
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

        // 当前 TIA Portal 主版本，可通过 --tia-major-version 参数重写
        private static string _tiaMajorVersion = "V18";

        // TIA Portal 安装根目录，优先从环境变量 TIA_PORTAL_ROOT 读取
        private static string _tiaPortalRoot =>
            Environment.GetEnvironmentVariable("TIA_PORTAL_ROOT") ?? @"D:\TIA BEN TI";

        // Dry-Run 模式：为 true 时只做校验和预览，不实际修改
        private static bool _isDryRun = false;

        // 自动备份：写入操作前自动备份项目
        private static bool _isAutoBackup = true;
        private static string _backupDir = "";

        // TIA Portal Openness DLL 路径（按版本动态解析）
        private static string[] _tiaDllPaths
        {
            get
            {
                var ver = _tiaMajorVersion;
                var baseDir = Path.Combine(_tiaPortalRoot, $"Portal {ver}", "PublicAPI", ver);
                // V21 使用模块化 DLL（net48 子目录），V18-V20 使用单体 DLL
                if (ver.Equals("V21", StringComparison.OrdinalIgnoreCase))
                    return new[] { Path.Combine(baseDir, "net48") };
                return new[] { baseDir };
            }
        }

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
            // 解析可选参数 --tia-major-version=V18 和 --dry-run
            var filteredArgs = new List<string>();
            for (int i = 0; i < args.Length; i++)
            {
                var arg = args[i];
                if (arg.Equals("--dry-run", StringComparison.OrdinalIgnoreCase))
                {
                    _isDryRun = true;
                    if (IsDebugEnabled)
                        Console.Error.WriteLine("[TiaWorker] Dry-Run mode enabled");
                }
                else if (arg.Equals("--no-auto-backup", StringComparison.OrdinalIgnoreCase))
                {
                    _isAutoBackup = false;
                }
                else if (arg.StartsWith("--backup-dir=", StringComparison.OrdinalIgnoreCase))
                {
                    _backupDir = arg.Substring("--backup-dir=".Length);
                }
                else if (arg.StartsWith("--tia-major-version=", StringComparison.OrdinalIgnoreCase))
                {
                    _tiaMajorVersion = arg.Substring("--tia-major-version=".Length);
                    if (IsDebugEnabled)
                        Console.Error.WriteLine($"[TiaWorker] TIA version: {_tiaMajorVersion}");
                }
                else if (arg.Equals("--tia-major-version", StringComparison.OrdinalIgnoreCase))
                {
                    // --tia-major-version V18 格式（取下一个 arg 作为值）
                    if (i + 1 < args.Length && !args[i + 1].StartsWith("-"))
                    {
                        _tiaMajorVersion = args[i + 1];
                        i++; // 跳过值
                        if (IsDebugEnabled)
                            Console.Error.WriteLine($"[TiaWorker] TIA version: {_tiaMajorVersion}");
                    }
                }
                else
                {
                    filteredArgs.Add(arg);
                }
            }

            args = filteredArgs.ToArray();
            if (args.Length < 2)
            {
                Console.WriteLine(JsonError("Usage: TiaWorker.exe [--tia-major-version=V18] [--dry-run] <command> <jsonFile>"));
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
                    case "list-blocks":
                        return ListBlocks(json);
                    case "save-project":
                        return SaveProject(json);
                    case "get-project-info":
                        return GetProjectInfo(json);
                    case "list-dbs":
                        return ListDbs(json);
                    case "list-tags":
                        return ListTags(json);
                    case "get-tags":
                        return GetTags(json);
                    case "add-tag":
                        return AddTag(json);
                    case "delete-tag":
                        return DeleteTag(json);
                    case "create-tag-table":
                        return CreateTagTable(json);
                    case "delete-tag-table":
                        return DeleteTagTable(json);
                    case "search-tag":
                        return SearchTag(json);
                    case "get-block-interface":
                        return GetBlockInterface(json);
                    case "get-block-details":
                        return GetBlockDetails(json);
                    case "delete-block":
                        return DeleteBlock(json);
                    case "compile-block":
                        return CompileBlock(json);
                    case "create-db":
                        return CreateDb(json);
                    case "delete-db":
                        return DeleteDb(json);
                    case "get-compiler-errors":
                        return GetCompilerErrors(json);
                    case "check-consistency":
                        return CheckConsistency(json);
                    case "export-all-xml":
                        return ExportAllXml(json);
                    case "close-project":
                        return CloseProject(json);
                    case "list-udts":
                        return ListUdts(json);
                    case "create-udt":
                        return CreateUdt(json);
                    case "delete-udt":
                        return DeleteUdt(json);
                    case "list-watch-tables":
                        return ListWatchTables(json);
                    case "create-watch-table":
                        return CreateWatchTable(json);
                    case "delete-watch-table":
                        return DeleteWatchTable(json);
                    case "find-unused-blocks":
                        return FindUnusedBlocks(json);
                    case "find-callers":
                        return FindCallers(json);
                    case "get-hardware-info":
                        return GetHardwareInfo(json);
                    case "create-project":
                        return CreateProject(json);
                    case "archive-project":
                        return ArchiveProject(json);
                    case "export-tags-csv":
                        return ExportTagsCsv(json);
                    case "check-tag-conflicts":
                        return CheckTagConflicts(json);
                    case "find-free-address":
                        return FindFreeAddress(json);
                    case "get-plc-status":
                        return GetPlcStatus(json);
                    case "go-online":
                        return GoOnline(json);
                    case "go-offline":
                        return GoOffline(json);
                    case "get-device-config":
                        return GetDeviceConfig(json);
                    case "get-rack-slot":
                        return GetRackSlot(json);
                    case "list-backups":
                        return ListBackups(json);
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

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
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

                AutoBackupProject(project);
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

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var compiler = plcSoftware.GetService<ICompilable>();
                var result = compiler.Compile();

                AutoBackupProject(project);
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
                var project = GetOrOpenProject(tia, input.ProjectPath);
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
                using (var tia = AttachOrCreate())
                {
                    var project = GetOrOpenProject(tia, input.ProjectPath);
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

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
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

            using (var tia = AttachOrCreate())
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

                PlcBlock block = null;

                // SCL 块通过 External Source API 创建（V18 唯一可靠方式）
                if (inputLanguage == "SCL")
                {
                    block = CreateBlockViaSclSource(plcSoftware, input.BlockName, inputBlockType);
                }
                else
                {
                    // LAD/FBD/STL: 尝试直接 Create
                    var createMethod = blocks.GetType().GetMethods()
                        .FirstOrDefault(m => m.Name == "Create" && m.GetParameters().Length >= 3);
                    if (createMethod != null)
                    {
                        var parms = createMethod.GetParameters();
                        var blockTypeValue = ResolveEnumByName(parms[1].ParameterType, inputBlockType == "FB" ? "FunctionBlock" : inputBlockType == "FC" ? "Function" : inputBlockType == "DB" ? "GlobalDB" : "OrganizationBlock");
                        var langValue = ResolveEnumByName(parms[2].ParameterType, inputLanguage);
                        if (blockTypeValue != null && langValue != null)
                        {
                            try { block = (PlcBlock)createMethod.Invoke(blocks, new object[] { input.BlockName, blockTypeValue, langValue }); }
                            catch { }
                        }
                    }

                    // 回退：V21 CreateFB
                    if (block == null && inputBlockType == "FB")
                    {
                        var createFbMethod = blocks.GetType().GetMethod("CreateFB");
                        if (createFbMethod != null)
                        {
                            var langParamType = createFbMethod.GetParameters()[3].ParameterType;
                            var langValue = ResolveEnumByName(langParamType, inputLanguage);
                            if (langValue != null)
                            {
                                var autoNum = input.BlockNumber <= 0;
                                var number = input.BlockNumber > 0 ? input.BlockNumber : 0;
                                try { block = (PlcBlock)createFbMethod.Invoke(blocks, new object[] { input.BlockName, autoNum, number, langValue }); }
                                catch { }
                            }
                        }
                    }
                }

                if (block == null)
                {
                    Console.WriteLine(JsonError($"Failed to create block '{input.BlockName}' ({inputBlockType}/{inputLanguage})"));
                    return 1;
                }

                AutoBackupProject(project);
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
        /// 通过 External Source API 创建 SCL 块（V18 唯一可靠方式）
        /// </summary>
        static PlcBlock CreateBlockViaSclSource(PlcSoftware plcSoftware, string blockName, string blockType)
        {
            // 生成最小 SCL 源码
            string sclCode;
            switch (blockType)
            {
                case "FB":
                    sclCode = $"FUNCTION_BLOCK \"{blockName}\"\n{{ S7_Optimized_Access := 'TRUE' }}\nVERSION : 0.1\n\nBEGIN\n    ;\nEND_FUNCTION_BLOCK";
                    break;
                case "FC":
                    sclCode = $"FUNCTION \"{blockName}\" : Void\n{{ S7_Optimized_Access := 'TRUE' }}\nVERSION : 0.1\n\nBEGIN\n    ;\nEND_FUNCTION";
                    break;
                case "OB":
                    sclCode = $"ORGANIZATION_BLOCK \"{blockName}\"\nTITLE = \"Main Program\"\nVERSION : 0.1\n\nBEGIN\n    ;\nEND_ORGANIZATION_BLOCK";
                    break;
                default:
                    return null;
            }

            // 写入临时 .scl 文件
            var tempFile = Path.Combine(Path.GetTempPath(), $"{blockName}.scl");
            try
            {
                File.WriteAllText(tempFile, sclCode, System.Text.Encoding.UTF8);

                // 通过 External Source 导入
                var extGroup = plcSoftware.ExternalSourceGroup;
                var extSources = extGroup.ExternalSources;

                // 删除同名已有 source（如果存在）
                try
                {
                    var existing = extSources.Find($"{blockName}.scl");
                    if (existing != null) existing.Delete();
                }
                catch { }

                var extSource = extSources.CreateFromFile($"{blockName}.scl", tempFile);
                var generated = extSource.GenerateBlocksFromSource(GenerateBlockOption.KeepOnError);

                // 清理 external source
                try { extSource.Delete(); } catch { }

                // 返回生成的块
                return plcSoftware.BlockGroup.Blocks.Find(blockName);
            }
            finally
            {
                try { File.Delete(tempFile); } catch { }
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
        /// 附加到已运行的 TIA Portal 实例（不需要管理员权限）。
        /// 如果没有运行中的实例，回退到 new TiaPortal()（需要管理员）。
        /// </summary>
        static TiaPortal AttachOrCreate()
        {
            try
            {
                var processes = TiaPortal.GetProcesses();
                if (processes.Count > 0)
                {
                    if (IsDebugEnabled)
                        Console.Error.WriteLine($"[TiaWorker] Attaching to running TIA Portal (PID: {processes[0].Id})");
                    return processes[0].Attach();
                }
            }
            catch (Exception ex)
            {
                if (IsDebugEnabled)
                    Console.Error.WriteLine($"[TiaWorker] GetProcesses failed: {ex.Message}");
            }

            // 没有运行中的实例，尝试启动新的（需要管理员权限）
            if (IsDebugEnabled)
                Console.Error.WriteLine("[TiaWorker] No running TIA Portal, creating new instance...");
            try
            {
                return new TiaPortal(TiaPortalMode.WithoutUserInterface);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[TiaWorker] Failed to create TIA Portal instance: {ex.Message}");
                throw new InvalidOperationException("无法创建 TIA Portal 实例。请确保 TIA Portal 已安装并以管理员身份运行。", ex);
            }
        }

        /// <summary>
        /// 获取已打开的项目，或打开指定路径的项目。
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

            // 没找到精确匹配，但如果只有一个项目，就用它
            if (tia.Projects.Count == 1)
            {
                var onlyProject = tia.Projects[0];
                if (IsDebugEnabled)
                    Console.Error.WriteLine($"[TiaWorker] Using the only open project: {onlyProject.Name}");
                return onlyProject;
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

            using (var tia = AttachOrCreate())
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

                AutoBackupProject(project);
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

            using (var tia = AttachOrCreate())
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

        // ═══════════════════════════════════════
        //  块列表 & 项目管理
        // ═══════════════════════════════════════

        static int ListBlocks(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var blocks = plcSoftware.BlockGroup.Blocks.Select(b =>
                {
                    var typeName = b.GetType().Name;
                    string blockType;
                    if (typeName.IndexOf("InstanceDB", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "InstanceDB";
                    else if (typeName.IndexOf("GlobalDB", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "GlobalDB";
                    else if (typeName.IndexOf("DB", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "DB";
                    else if (typeName.IndexOf("OB", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "OB";
                    else if (typeName.IndexOf("FB", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "FB";
                    else if (typeName.IndexOf("FC", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "FC";
                    else blockType = typeName;

                    return new
                    {
                        name = b.Name,
                        number = b.Number,
                        type = blockType,
                        language = b.ProgrammingLanguage.ToString()
                    };
                }).ToArray();

                Console.WriteLine(JsonOk(new { count = blocks.Length, blocks }));
                return 0;
            }
        }

        static int SaveProject(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                project.Save();
                Console.WriteLine(JsonOk(new { saved = project.Name }));
                return 0;
            }
        }

        static int GetProjectInfo(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                Console.WriteLine(JsonOk(new
                {
                    name = project.Name,
                    path = project.Path?.FullName,
                    deviceCount = project.Devices.Count
                }));
                return 0;
            }
        }

        static int ListDbs(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var dbs = plcSoftware.BlockGroup.Blocks
                    .Where(b =>
                    {
                        var t = b.GetType().Name;
                        return t.IndexOf("DB", StringComparison.OrdinalIgnoreCase) >= 0;
                    })
                    .Select(b => new
                    {
                        name = b.Name,
                        number = b.Number,
                        type = b.GetType().Name.IndexOf("Instance", StringComparison.OrdinalIgnoreCase) >= 0 ? "InstanceDB" : "GlobalDB"
                    }).ToArray();

                Console.WriteLine(JsonOk(new { count = dbs.Length, dbs }));
                return 0;
            }
        }

        // ═══════════════════════════════════════
        //  标签表管理
        // ═══════════════════════════════════════

        static int ListTags(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var tables = plcSoftware.TagTableGroup.TagTables
                    .Select(t => new { name = t.Name, tagCount = t.Tags.Count })
                    .ToArray();

                Console.WriteLine(JsonOk(new { tables }));
                return 0;
            }
        }

        static int GetTags(string json)
        {
            var input = Json.Deserialize<TagTableInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.TagTableName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or TagTableName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var table = plcSoftware.TagTableGroup.TagTables.Find(input.TagTableName);
                if (table == null)
                {
                    Console.WriteLine(JsonError($"Tag table '{input.TagTableName}' not found"));
                    return 1;
                }

                var tags = table.Tags.Select(t => new
                {
                    name = t.Name,
                    dataType = t.DataTypeName,
                    address = t.LogicalAddress
                }).ToArray();

                Console.WriteLine(JsonOk(new { tableName = table.Name, tags }));
                return 0;
            }
        }

        static int AddTag(string json)
        {
            var input = Json.Deserialize<AddTagInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.TagTableName) ||
                string.IsNullOrEmpty(input?.TagName) || string.IsNullOrEmpty(input?.DataType))
            {
                Console.WriteLine(JsonError("Missing ProjectPath, TagTableName, TagName, or DataType"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var table = plcSoftware.TagTableGroup.TagTables.Find(input.TagTableName);
                if (table == null)
                {
                    Console.WriteLine(JsonError($"Tag table '{input.TagTableName}' not found"));
                    return 1;
                }

                var tag = table.Tags.Create(input.TagName, input.DataType, input.LogicalAddress ?? "");
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new
                {
                    tagName = tag.Name,
                    dataType = tag.DataTypeName,
                    address = tag.LogicalAddress
                }));
                return 0;
            }
        }

        static int DeleteTag(string json)
        {
            var input = Json.Deserialize<DeleteTagInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.TagTableName) ||
                string.IsNullOrEmpty(input?.TagName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath, TagTableName, or TagName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var table = plcSoftware.TagTableGroup.TagTables.Find(input.TagTableName);
                if (table == null)
                {
                    Console.WriteLine(JsonError($"Tag table '{input.TagTableName}' not found"));
                    return 1;
                }

                var tag = table.Tags.Find(input.TagName);
                if (tag == null)
                {
                    Console.WriteLine(JsonError($"Tag '{input.TagName}' not found in '{input.TagTableName}'"));
                    return 1;
                }

                tag.Delete();
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new { deleted = input.TagName, table = input.TagTableName }));
                return 0;
            }
        }

        static int CreateTagTable(string json)
        {
            var input = Json.Deserialize<TagTableInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.TagTableName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or TagTableName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var table = plcSoftware.TagTableGroup.TagTables.Create(input.TagTableName);
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new { tableName = table.Name }));
                return 0;
            }
        }

        static int SearchTag(string json)
        {
            var input = Json.Deserialize<SearchTagInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.Query))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or Query"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var query = input.Query.ToLowerInvariant();
                var results = new List<object>();

                foreach (var table in plcSoftware.TagTableGroup.TagTables)
                {
                    foreach (var tag in table.Tags)
                    {
                        if (tag.Name.ToLowerInvariant().Contains(query))
                        {
                            results.Add(new
                            {
                                table = table.Name,
                                name = tag.Name,
                                dataType = tag.DataTypeName,
                                address = tag.LogicalAddress
                            });
                        }
                    }
                }

                Console.WriteLine(JsonOk(new { query = input.Query, count = results.Count, results }));
                return 0;
            }
        }

        static int DeleteTagTable(string json)
        {
            var input = Json.Deserialize<TagTableInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.TagTableName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or TagTableName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var table = plcSoftware.TagTableGroup.TagTables.Find(input.TagTableName);
                if (table == null)
                {
                    Console.WriteLine(JsonError($"Tag table '{input.TagTableName}' not found"));
                    return 1;
                }

                table.Delete();
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new { deleted = input.TagTableName }));
                return 0;
            }
        }

        // ═══════════════════════════════════════
        //  UDT 管理（反射方式，兼容 V18）
        // ═══════════════════════════════════════

        static int ListUdts(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                // 反射获取 TypeGroup.Types
                var typeGroupProp = plcSoftware.GetType().GetProperty("TypeGroup");
                if (typeGroupProp == null)
                {
                    Console.WriteLine(JsonError("TypeGroup not available in this TIA version"));
                    return 1;
                }
                var typeGroup = typeGroupProp.GetValue(plcSoftware);
                var typesProp = typeGroup.GetType().GetProperty("Types");
                if (typesProp == null)
                {
                    Console.WriteLine(JsonError("Types property not available"));
                    return 1;
                }
                var types = typesProp.GetValue(typeGroup);

                var udts = new List<object>();
                foreach (var t in (System.Collections.IEnumerable)types)
                {
                    var nameProp = t.GetType().GetProperty("Name");
                    var name = nameProp?.GetValue(t)?.ToString() ?? "?";
                    udts.Add(new { name });
                }

                Console.WriteLine(JsonOk(new { count = udts.Count, udts }));
                return 0;
            }
        }

        static int CreateUdt(string json)
        {
            var input = Json.Deserialize<UdtInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.UdtName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or UdtName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                // 反射获取 TypeGroup.Types
                var typeGroupProp = plcSoftware.GetType().GetProperty("TypeGroup");
                if (typeGroupProp == null)
                {
                    Console.WriteLine(JsonError("TypeGroup not available in this TIA version"));
                    return 1;
                }
                var typeGroup = typeGroupProp.GetValue(plcSoftware);
                var typesProp = typeGroup.GetType().GetProperty("Types");
                if (typesProp == null)
                {
                    Console.WriteLine(JsonError("Types property not available"));
                    return 1;
                }
                var types = typesProp.GetValue(typeGroup);

                // 尝试直接 Create(name) 方法
                var createMethod = types.GetType().GetMethods()
                    .FirstOrDefault(m => m.Name == "Create" && m.GetParameters().Length == 1
                        && m.GetParameters()[0].ParameterType == typeof(string));

                if (createMethod != null)
                {
                    var udt = createMethod.Invoke(types, new object[] { input.UdtName });
                    project.Save();
                    Console.WriteLine(JsonOk(new { udtName = input.UdtName }));
                    return 0;
                }

                // 回退：通过 External Source API 创建（写最小 TYPE...END_TYPE 文件导入）
                try
                {
                    var sclContent = $"TYPE \"{input.UdtName}\"\n  STRUCT\n    Placeholder : Bool;\n  END_STRUCT;\nEND_TYPE\n";
                    var tempFile = Path.Combine(Path.GetTempPath(), $"udt_{Guid.NewGuid():N}.scl");
                    File.WriteAllText(tempFile, sclContent, System.Text.Encoding.UTF8);
                    try
                    {
                        var extGroup = plcSoftware.ExternalSourceGroup;
                        var extSources = extGroup.ExternalSources;
                        var extSource = extSources.CreateFromFile(Path.GetFileName(tempFile), tempFile);
                        extSource.GenerateBlocksFromSource(GenerateBlockOption.None);
                        project.Save();
                        Console.WriteLine(JsonOk(new { udtName = input.UdtName, method = "external_source" }));
                        return 0;
                    }
                    finally
                    {
                        try { File.Delete(tempFile); } catch { }
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonError($"Failed to create UDT: {ex.Message}"));
                    return 1;
                }
            }
        }

        static int DeleteUdt(string json)
        {
            var input = Json.Deserialize<UdtInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.UdtName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or UdtName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var typeGroupProp = plcSoftware.GetType().GetProperty("TypeGroup");
                if (typeGroupProp == null)
                {
                    Console.WriteLine(JsonError("TypeGroup not available in this TIA version"));
                    return 1;
                }
                var typeGroup = typeGroupProp.GetValue(plcSoftware);
                var typesProp = typeGroup.GetType().GetProperty("Types");
                var types = typesProp.GetValue(typeGroup);

                // 查找指定 UDT
                object target = null;
                foreach (var t in (System.Collections.IEnumerable)types)
                {
                    var nameProp = t.GetType().GetProperty("Name");
                    var name = nameProp?.GetValue(t)?.ToString() ?? "";
                    if (name.Equals(input.UdtName, StringComparison.OrdinalIgnoreCase))
                    {
                        target = t;
                        break;
                    }
                }

                if (target == null)
                {
                    Console.WriteLine(JsonError($"UDT '{input.UdtName}' not found"));
                    return 1;
                }

                var deleteMethod = target.GetType().GetMethod("Delete", Type.EmptyTypes);
                if (deleteMethod == null)
                {
                    Console.WriteLine(JsonError("Delete method not available on UDT object"));
                    return 1;
                }

                deleteMethod.Invoke(target, null);
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new { deleted = input.UdtName }));
                return 0;
            }
        }

        // ═══════════════════════════════════════
        //  Watch 表管理（反射方式，兼容 V18）
        // ═══════════════════════════════════════

        static int ListWatchTables(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                // 反射获取 WatchAndForceTableGroup.WatchTables
                var groupProp = plcSoftware.GetType().GetProperty("WatchAndForceTableGroup");
                if (groupProp == null)
                {
                    Console.WriteLine(JsonError("WatchAndForceTableGroup not available in this TIA version"));
                    return 1;
                }
                var group = groupProp.GetValue(plcSoftware);
                var tablesProp = group.GetType().GetProperty("WatchTables");
                if (tablesProp == null)
                {
                    Console.WriteLine(JsonError("WatchTables property not available"));
                    return 1;
                }
                var tables = tablesProp.GetValue(group);

                var watchTables = new List<object>();
                foreach (var t in (System.Collections.IEnumerable)tables)
                {
                    var nameProp = t.GetType().GetProperty("Name");
                    var name = nameProp?.GetValue(t)?.ToString() ?? "?";
                    watchTables.Add(new { name });
                }

                Console.WriteLine(JsonOk(new { count = watchTables.Count, watchTables }));
                return 0;
            }
        }

        static int CreateWatchTable(string json)
        {
            var input = Json.Deserialize<WatchTableInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.WatchTableName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or WatchTableName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var groupProp = plcSoftware.GetType().GetProperty("WatchAndForceTableGroup");
                if (groupProp == null)
                {
                    Console.WriteLine(JsonError("WatchAndForceTableGroup not available in this TIA version"));
                    return 1;
                }
                var group = groupProp.GetValue(plcSoftware);
                var tablesProp = group.GetType().GetProperty("WatchTables");
                if (tablesProp == null)
                {
                    Console.WriteLine(JsonError("WatchTables property not available"));
                    return 1;
                }
                var tables = tablesProp.GetValue(group);

                // 调用 Create(name)
                var createMethod = tables.GetType().GetMethods()
                    .FirstOrDefault(m => m.Name == "Create" && m.GetParameters().Length == 1
                        && m.GetParameters()[0].ParameterType == typeof(string));

                if (createMethod == null)
                {
                    Console.WriteLine(JsonError("Create method not found on WatchTables"));
                    return 1;
                }

                var watchTable = createMethod.Invoke(tables, new object[] { input.WatchTableName });
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new { watchTableName = input.WatchTableName }));
                return 0;
            }
        }

        static int DeleteWatchTable(string json)
        {
            var input = Json.Deserialize<WatchTableInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.WatchTableName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or WatchTableName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var groupProp = plcSoftware.GetType().GetProperty("WatchAndForceTableGroup");
                if (groupProp == null)
                {
                    Console.WriteLine(JsonError("WatchAndForceTableGroup not available in this TIA version"));
                    return 1;
                }
                var group = groupProp.GetValue(plcSoftware);
                var tablesProp = group.GetType().GetProperty("WatchTables");
                if (tablesProp == null)
                {
                    Console.WriteLine(JsonError("WatchTables property not available"));
                    return 1;
                }
                var tables = tablesProp.GetValue(group);

                // 查找指定 Watch 表
                object target = null;
                foreach (var t in (System.Collections.IEnumerable)tables)
                {
                    var nameProp = t.GetType().GetProperty("Name");
                    var name = nameProp?.GetValue(t)?.ToString() ?? "";
                    if (name.Equals(input.WatchTableName, StringComparison.OrdinalIgnoreCase))
                    {
                        target = t;
                        break;
                    }
                }

                if (target == null)
                {
                    Console.WriteLine(JsonError($"Watch table '{input.WatchTableName}' not found"));
                    return 1;
                }

                var deleteMethod = target.GetType().GetMethod("Delete", Type.EmptyTypes);
                if (deleteMethod == null)
                {
                    Console.WriteLine(JsonError("Delete method not available on WatchTable object"));
                    return 1;
                }

                deleteMethod.Invoke(target, null);
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new { deleted = input.WatchTableName }));
                return 0;
            }
        }

        // ═══════════════════════════════════════
        //  块接口读取 & DB 管理
        // ═══════════════════════════════════════

        static int GetBlockDetails(string json)
        {
            var input = Json.Deserialize<BlockNameInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.BlockName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or BlockName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var block = plcSoftware.BlockGroup.Blocks.Find(input.BlockName);
                if (block == null)
                {
                    Console.WriteLine(JsonError($"Block '{input.BlockName}' not found"));
                    return 1;
                }

                var typeName = block.GetType().Name;
                string blockType;
                if (typeName.IndexOf("InstanceDB", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "InstanceDB";
                else if (typeName.IndexOf("GlobalDB", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "GlobalDB";
                else if (typeName.IndexOf("OB", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "OB";
                else if (typeName.IndexOf("FB", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "FB";
                else if (typeName.IndexOf("FC", StringComparison.OrdinalIgnoreCase) >= 0) blockType = "FC";
                else blockType = typeName;

                bool isConsistent = false;
                try { isConsistent = block.IsConsistent; } catch { }

                Console.WriteLine(JsonOk(new
                {
                    name = block.Name,
                    number = block.Number,
                    type = blockType,
                    language = block.ProgrammingLanguage.ToString(),
                    isConsistent
                }));
                return 0;
            }
        }

        static int DeleteBlock(string json)
        {
            var input = Json.Deserialize<BlockNameInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.BlockName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or BlockName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var block = plcSoftware.BlockGroup.Blocks.Find(input.BlockName);
                if (block == null)
                {
                    Console.WriteLine(JsonError($"Block '{input.BlockName}' not found"));
                    return 1;
                }

                var name = block.Name;
                var number = block.Number;
                block.Delete();
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new { deleted = name, number }));
                return 0;
            }
        }

        static int CompileBlock(string json)
        {
            var input = Json.Deserialize<BlockNameInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.BlockName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or BlockName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var block = plcSoftware.BlockGroup.Blocks.Find(input.BlockName);
                if (block == null)
                {
                    Console.WriteLine(JsonError($"Block '{input.BlockName}' not found"));
                    return 1;
                }

                var compilable = block.GetService<ICompilable>();
                if (compilable == null)
                {
                    Console.WriteLine(JsonError($"Block '{input.BlockName}' is not compilable"));
                    return 1;
                }

                var result = compilable.Compile();
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new
                {
                    blockName = input.BlockName,
                    success = result.State == CompilerResultState.Success,
                    errors = result.ErrorCount,
                    warnings = result.WarningCount
                }));
                return result.State == CompilerResultState.Success ? 0 : 1;
            }
        }

        static int DeleteDb(string json)
        {
            var input = Json.Deserialize<BlockNameInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.BlockName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or BlockName (DB name)"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var block = plcSoftware.BlockGroup.Blocks.Find(input.BlockName);
                if (block == null)
                {
                    Console.WriteLine(JsonError($"DB '{input.BlockName}' not found"));
                    return 1;
                }

                var typeName = block.GetType().Name;
                if (typeName.IndexOf("DB", StringComparison.OrdinalIgnoreCase) < 0)
                {
                    Console.WriteLine(JsonError($"'{input.BlockName}' is not a DB (type: {typeName})"));
                    return 1;
                }

                var name = block.Name;
                var number = block.Number;
                block.Delete();
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new { deleted = name, number }));
                return 0;
            }
        }

        static int GetCompilerErrors(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var compilable = plcSoftware.GetService<ICompilable>();
                var result = compilable.Compile();

                var messages = new List<object>();
                try
                {
                    foreach (var msg in result.Messages)
                    {
                        messages.Add(new
                        {
                            path = msg.Path,
                            description = msg.Description,
                            state = msg.State.ToString(),
                            errors = msg.ErrorCount,
                            warnings = msg.WarningCount
                        });
                    }
                }
                catch { }

                Console.WriteLine(JsonOk(new
                {
                    success = result.State == CompilerResultState.Success,
                    errors = result.ErrorCount,
                    warnings = result.WarningCount,
                    messages
                }));
                return 0;
            }
        }

        static int CheckConsistency(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var results = new List<object>();
                int inconsistentCount = 0;
                foreach (var block in plcSoftware.BlockGroup.Blocks)
                {
                    bool consistent = false;
                    try { consistent = block.IsConsistent; } catch { }
                    if (!consistent) inconsistentCount++;

                    results.Add(new
                    {
                        name = block.Name,
                        number = block.Number,
                        isConsistent = consistent
                    });
                }

                Console.WriteLine(JsonOk(new
                {
                    total = results.Count,
                    consistent = results.Count - inconsistentCount,
                    inconsistent = inconsistentCount,
                    blocks = results
                }));
                return 0;
            }
        }

        static int ExportAllXml(string json)
        {
            var input = Json.Deserialize<ExportAllInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.OutputDir))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or OutputDir"));
                return 1;
            }

            Directory.CreateDirectory(input.OutputDir);

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var exported = new List<string>();
                var failed = new List<string>();

                foreach (var block in plcSoftware.BlockGroup.Blocks)
                {
                    var filePath = Path.Combine(input.OutputDir, $"{block.Name}.xml");
                    try
                    {
                        var exportMethod = block.GetType().GetMethod("Export",
                            new[] { typeof(FileInfo), typeof(ExportOptions) });

                        if (exportMethod != null)
                        {
                            exportMethod.Invoke(block, new object[] { new FileInfo(filePath), ExportOptions.WithDefaults });
                        }
                        else
                        {
                            var svc = CallReflectedService(block, "Siemens.Engineering.SW.Blocks.IConvertible");
                            if (svc != null)
                            {
                                var m = svc.GetType().GetMethod("Export");
                                m.Invoke(svc, new object[] { new FileInfo(filePath), 1 });
                            }
                        }
                        exported.Add(block.Name);
                    }
                    catch
                    {
                        failed.Add(block.Name);
                    }
                }

                Console.WriteLine(JsonOk(new
                {
                    outputDir = input.OutputDir,
                    exported = exported.Count,
                    failed = failed.Count,
                    failedBlocks = failed.ToArray()
                }));
                return 0;
            }
        }

        static int CloseProject(string json)
        {
            var input = Json.Deserialize<CloseProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);

                if (input.Save)
                    project.Save();

                project.Close();

                Console.WriteLine(JsonOk(new { closed = project.Name, saved = input.Save }));
                return 0;
            }
        }

        // ═══════════════════════════════════════
        //  交叉引用分析
        // ═══════════════════════════════════════

        static int FindUnusedBlocks(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                // 收集所有块
                var allBlocks = plcSoftware.BlockGroup.Blocks.ToList();
                var calledNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

                // 对每个块获取引用，找出被调用的块
                foreach (var block in allBlocks)
                {
                    try
                    {
                        var refs = block.GetType().GetMethod("GetCrossReferences");
                        if (refs != null)
                        {
                            var crossRefs = refs.Invoke(block, null) as System.Collections.IEnumerable;
                            if (crossRefs != null)
                            {
                                foreach (var cr in crossRefs)
                                {
                                    var refObjProp = cr.GetType().GetProperty("ReferenceObject");
                                    if (refObjProp != null)
                                    {
                                        var refObj = refObjProp.GetValue(cr);
                                        if (refObj is PlcBlock refBlock)
                                        {
                                            calledNames.Add(refBlock.Name);
                                        }
                                    }
                                }
                            }
                        }
                    }
                    catch { }
                }

                // 未被引用的块（排除 OB）
                var unused = allBlocks
                    .Where(b =>
                    {
                        var typeName = b.GetType().Name;
                        if (typeName.IndexOf("OB", StringComparison.OrdinalIgnoreCase) >= 0) return false;
                        return !calledNames.Contains(b.Name);
                    })
                    .Select(b => new { name = b.Name, number = b.Number, type = b.GetType().Name })
                    .ToArray();

                Console.WriteLine(JsonOk(new { total = allBlocks.Count, unusedCount = unused.Length, unused }));
                return 0;
            }
        }

        static int FindCallers(string json)
        {
            var input = Json.Deserialize<BlockNameInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.BlockName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or BlockName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var targetBlock = plcSoftware.BlockGroup.Blocks.Find(input.BlockName);
                if (targetBlock == null)
                {
                    Console.WriteLine(JsonError($"Block '{input.BlockName}' not found"));
                    return 1;
                }

                var callers = new List<object>();
                foreach (var block in plcSoftware.BlockGroup.Blocks)
                {
                    if (block.Name.Equals(input.BlockName, StringComparison.OrdinalIgnoreCase)) continue;
                    try
                    {
                        var refs = block.GetType().GetMethod("GetCrossReferences");
                        if (refs != null)
                        {
                            var crossRefs = refs.Invoke(block, null) as System.Collections.IEnumerable;
                            if (crossRefs != null)
                            {
                                foreach (var cr in crossRefs)
                                {
                                    var refObjProp = cr.GetType().GetProperty("ReferenceObject");
                                    if (refObjProp != null)
                                    {
                                        var refObj = refObjProp.GetValue(cr);
                                        if (refObj is PlcBlock refBlock && refBlock.Name.Equals(input.BlockName, StringComparison.OrdinalIgnoreCase))
                                        {
                                            callers.Add(new { name = block.Name, number = block.Number });
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    catch { }
                }

                Console.WriteLine(JsonOk(new { target = input.BlockName, callerCount = callers.Count, callers }));
                return 0;
            }
        }

        static int CreateProject(string json)
        {
            var input = Json.Deserialize<CreateProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectName) || string.IsNullOrEmpty(input?.ParentDirectory))
            {
                Console.WriteLine(JsonError("Missing ProjectName or ParentDirectory"));
                return 1;
            }

            var parentDir = new DirectoryInfo(input.ParentDirectory);
            if (!parentDir.Exists)
            {
                Console.WriteLine(JsonError($"Directory not found: {input.ParentDirectory}"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = tia.Projects.Create(parentDir, input.ProjectName);
                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new
                {
                    name = project.Name,
                    path = project.Path?.FullName
                }));
                return 0;
            }
        }

        static int ArchiveProject(string json)
        {
            var input = Json.Deserialize<ArchiveProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.OutputDir))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or OutputDir"));
                return 1;
            }

            var outputDir = new DirectoryInfo(input.OutputDir);
            if (!outputDir.Exists)
                Directory.CreateDirectory(input.OutputDir);

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var archiveName = input.ArchiveName ?? project.Name;

                // V18: project.Archive(DirectoryInfo, string, ArchivationMode) 或反射
                var archiveMethod = project.GetType().GetMethods()
                    .FirstOrDefault(m => m.Name == "Archive" && m.GetParameters().Length >= 2);

                if (archiveMethod != null)
                {
                    var parms = archiveMethod.GetParameters();
                    if (parms.Length == 3)
                    {
                        // Archive(DirectoryInfo, string, ArchivationMode)
                        var modeType = parms[2].ParameterType;
                        var modeValue = Enum.GetValues(modeType).GetValue(0); // 默认模式
                        archiveMethod.Invoke(project, new object[] { outputDir, archiveName, modeValue });
                    }
                    else
                    {
                        archiveMethod.Invoke(project, new object[] { outputDir, archiveName });
                    }
                }
                else
                {
                    Console.WriteLine(JsonError("Archive method not available in this TIA version"));
                    return 1;
                }

                Console.WriteLine(JsonOk(new
                {
                    projectName = project.Name,
                    archiveName,
                    outputDir = input.OutputDir
                }));
                return 0;
            }
        }

        static int GetHardwareInfo(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            {
                Console.WriteLine(JsonError("Missing ProjectPath"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var devices = new List<object>();

                foreach (var device in project.Devices)
                {
                    var items = new List<object>();
                    foreach (var item in device.DeviceItems)
                    {
                        CollectDeviceItems(item, items, 0);
                    }
                    devices.Add(new
                    {
                        name = device.Name,
                        type = device.TypeIdentifier,
                        items
                    });
                }

                Console.WriteLine(JsonOk(new { deviceCount = devices.Count, devices }));
                return 0;
            }
        }

        static void CollectDeviceItems(DeviceItem item, List<object> results, int depth)
        {
            if (depth > 5) return;
            results.Add(new
            {
                name = item.Name,
                type = item.TypeIdentifier ?? "",
                depth
            });
            foreach (var child in item.DeviceItems)
            {
                CollectDeviceItems(child, results, depth + 1);
            }
        }

        static int GetBlockInterface(string json)
        {
            var input = Json.Deserialize<BlockNameInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.BlockName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or BlockName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var block = plcSoftware.BlockGroup.Blocks.Find(input.BlockName);
                if (block == null)
                {
                    Console.WriteLine(JsonError($"Block '{input.BlockName}' not found"));
                    return 1;
                }

                // 导出到临时 XML 文件
                var tempFile = Path.Combine(Path.GetTempPath(), $"tia_iface_{Guid.NewGuid():N}.xml");
                try
                {
                    // 使用 Export 方法（V18 直接在 PlcBlock 上）
                    var exportMethod = block.GetType().GetMethod("Export",
                        new[] { typeof(FileInfo), typeof(ExportOptions) });

                    if (exportMethod != null)
                    {
                        exportMethod.Invoke(block, new object[] { new FileInfo(tempFile), ExportOptions.WithDefaults });
                    }
                    else
                    {
                        // 回退：IConvertible 反射
                        var svc = CallReflectedService(block, "Siemens.Engineering.SW.Blocks.IConvertible");
                        if (svc == null)
                        {
                            Console.WriteLine(JsonError("Export not supported for this block"));
                            return 1;
                        }
                        var svcExport = svc.GetType().GetMethod("Export");
                        svcExport.Invoke(svc, new object[] { new FileInfo(tempFile), 1 });
                    }

                    // 解析 XML 中的 Interface 部分
                    var doc = XDocument.Load(tempFile);
                    var sections = new List<object>();

                    foreach (var sectionEl in doc.Descendants().Where(e => e.Name.LocalName == "Section"))
                    {
                        var sectionName = sectionEl.Attribute("Name")?.Value;
                        if (string.IsNullOrEmpty(sectionName)) continue;

                        var members = sectionEl.Elements()
                            .Where(e => e.Name.LocalName == "Member")
                            .Select(m => new
                            {
                                name = m.Attribute("Name")?.Value,
                                dataType = m.Attribute("Datatype")?.Value
                            }).ToArray();

                        if (members.Length > 0)
                        {
                            sections.Add(new { section = sectionName, members });
                        }
                    }

                    Console.WriteLine(JsonOk(new { blockName = input.BlockName, sections }));
                    return 0;
                }
                finally
                {
                    try { File.Delete(tempFile); } catch { }
                }
            }
        }

        static int CreateDb(string json)
        {
            var input = Json.Deserialize<CreateDbInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.DbName))
            {
                Console.WriteLine(JsonError("Missing ProjectPath or DbName"));
                return 1;
            }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plcSoftware = GetPlcSoftware(project);
                if (plcSoftware == null)
                {
                    Console.WriteLine(JsonError("No PLC device found"));
                    return 1;
                }

                var blocks = plcSoftware.BlockGroup.Blocks;

                // 尝试找 Create 方法（2 或 3 参数）
                PlcBlock db = null;
                var methods = blocks.GetType().GetMethods().Where(m => m.Name == "Create").ToArray();

                // 先尝试 3 参数: Create(name, PlcBlockType.GlobalDB, PlcProgrammingLanguage.DB)
                var create3 = methods.FirstOrDefault(m => m.GetParameters().Length == 3);
                if (create3 != null)
                {
                    var parms = create3.GetParameters();
                    var blockTypeVal = ResolveEnumByName(parms[1].ParameterType, "GlobalDB");
                    // DB 的语言尝试 "DB" 或第一个可用值
                    var langVal = ResolveEnumByName(parms[2].ParameterType, "DB");
                    if (langVal == null) langVal = ResolveEnumByName(parms[2].ParameterType, "SCL");

                    if (blockTypeVal != null && langVal != null)
                    {
                        db = (PlcBlock)create3.Invoke(blocks, new object[] { input.DbName, blockTypeVal, langVal });
                    }
                }

                // 回退：2 参数
                if (db == null)
                {
                    var create2 = methods.FirstOrDefault(m => m.GetParameters().Length == 2);
                    if (create2 != null)
                    {
                        var parms = create2.GetParameters();
                        var blockTypeVal = ResolveEnumByName(parms[1].ParameterType, "GlobalDB");
                        if (blockTypeVal != null)
                        {
                            db = (PlcBlock)create2.Invoke(blocks, new object[] { input.DbName, blockTypeVal });
                        }
                    }
                }

                if (db == null)
                {
                    Console.WriteLine(JsonError("Failed to create DB — no compatible Create method found"));
                    return 1;
                }

                AutoBackupProject(project);
                project.Save();

                Console.WriteLine(JsonOk(new { dbName = db.Name, number = db.Number }));
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

        // ── P3-11: CSV 导出 ──

        static int ExportTagsCsv(string json)
        {
            var input = Json.Deserialize<ExportTagsInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath) || string.IsNullOrEmpty(input?.OutputPath))
            { Console.WriteLine(JsonError("Missing ProjectPath or OutputPath")); return 1; }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plc = GetPlcSoftware(project);
                if (plc == null) { Console.WriteLine(JsonError("No PLC device found")); return 1; }

                try
                {
                    var tagMgr = plc.GetService<TagTableManager>();
                    if (tagMgr == null) { Console.WriteLine(JsonError("TagTableManager not available")); return 1; }
                    var tables = tagMgr.TagTables;

                    var lines = new List<string> { "TableName,TagName,DataType,Address,Comment" };
                    int total = 0;
                    foreach (var table in tables)
                    {
                        foreach (var tag in table.Tags)
                        {
                            var addr = tag.LogicalAddress ?? "";
                            var comment = (tag.Comment ?? "").Replace("\"", "\"\"");
                            lines.Add($"\"{table.Name}\",\"{tag.Name}\",\"{tag.DataTypeName}\",\"{addr}\",\"{comment}\"");
                            total++;
                        }
                    }

                    File.WriteAllLines(input.OutputPath, lines);
                    Console.WriteLine(JsonOk(new { file = input.OutputPath, count = total, format = "csv" }));
                    return 0;
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonError($"Export failed: {ex.Message}"));
                    return 1;
                }
            }
        }

        // ── P3-12: 标签冲突检测 ──

        static int CheckTagConflicts(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            { Console.WriteLine(JsonError("Missing ProjectPath")); return 1; }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plc = GetPlcSoftware(project);
                if (plc == null) { Console.WriteLine(JsonError("No PLC device found")); return 1; }

                try
                {
                    var tagMgr = plc.GetService<TagTableManager>();
                    if (tagMgr == null) { Console.WriteLine(JsonError("TagTableManager not available")); return 1; }

                    var addressMap = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
                    foreach (var table in tagMgr.TagTables)
                    {
                        foreach (var tag in table.Tags)
                        {
                            var addr = tag.LogicalAddress ?? "";
                            if (string.IsNullOrEmpty(addr)) continue;
                            if (!addressMap.ContainsKey(addr))
                                addressMap[addr] = new List<string>();
                            addressMap[addr].Add($"{table.Name}.{tag.Name}");
                        }
                    }

                    var conflicts = addressMap
                        .Where(kv => kv.Value.Count > 1)
                        .Select(kv => new { address = kv.Key, tags = kv.Value })
                        .ToList();

                    Console.WriteLine(JsonOk(new { totalConflicts = conflicts.Count, conflicts }));
                    return 0;
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonError($"Conflict check failed: {ex.Message}"));
                    return 1;
                }
            }
        }

        static int FindFreeAddress(string json)
        {
            var input = Json.Deserialize<FindFreeAddressInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            { Console.WriteLine(JsonError("Missing ProjectPath")); return 1; }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                var plc = GetPlcSoftware(project);
                if (plc == null) { Console.WriteLine(JsonError("No PLC device found")); return 1; }

                try
                {
                    var tagMgr = plc.GetService<TagTableManager>();
                    if (tagMgr == null) { Console.WriteLine(JsonError("TagTableManager not available")); return 1; }

                    var area = string.IsNullOrEmpty(input.Area) ? "M" : input.Area.ToUpper();
                    var startByte = input.StartByte;
                    var used = new HashSet<int>();

                    foreach (var table in tagMgr.TagTables)
                    {
                        foreach (var tag in table.Tags)
                        {
                            var addr = tag.LogicalAddress ?? "";
                            if (addr.StartsWith($"%{area}") || addr.StartsWith($"%{area.ToLower()}"))
                            {
                                var parsed = ParseAddressOffset(addr);
                                if (parsed.HasValue) used.Add(parsed.Value);
                            }
                        }
                    }

                    // 找到第一个空闲字节
                    var free = startByte;
                    while (used.Contains(free)) free++;

                    Console.WriteLine(JsonOk(new { area, freeByte = free, address = $"%{area}W{free}" }));
                    return 0;
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonError($"FindFreeAddress failed: {ex.Message}"));
                    return 1;
                }
            }
        }

        static int? ParseAddressOffset(string addr)
        {
            try
            {
                // 解析 %MW100 → 100, %M100.0 → 100
                var m = System.Text.RegularExpressions.Regex.Match(addr, @"%[A-Za-z]+(\d+)");
                if (m.Success && int.TryParse(m.Groups[1].Value, out var offset))
                    return offset;
                return null;
            }
            catch { return null; }
        }

        // ── P2-8: 诊断工具 ──

        static int GetPlcStatus(string json)
        {
            var input = Json.Deserialize<DeviceInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            { Console.WriteLine(JsonError("Missing ProjectPath")); return 1; }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                try
                {
                    var device = FindDevice(project, input.DeviceName);
                    if (device == null) { Console.WriteLine(JsonError("Device not found")); return 1; }

                    // 尝试通过 GetService 获取在线状态（可能不支持）
                    var status = "UNKNOWN";
                    try
                    {
                        var swContainer = device.GetService<SoftwareContainer>();
                        if (swContainer?.Software is PlcSoftware plc)
                        {
                            var online = plc.GetService("Siemens.Engineering.IOnlineProvider");
                            if (online != null)
                            {
                                var stateProp = online.GetType().GetProperty("State");
                                if (stateProp != null) status = stateProp.GetValue(online)?.ToString() ?? "UNKNOWN";
                            }
                        }
                    }
                    catch { /* online service not available */ }

                    Console.WriteLine(JsonOk(new { device = device.Name, status, online = status }));
                    return 0;
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonError($"GetPlcStatus failed: {ex.Message}"));
                    return 1;
                }
            }
        }

        static int GoOnline(string json)
        {
            var input = Json.Deserialize<DeviceInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            { Console.WriteLine(JsonError("Missing ProjectPath")); return 1; }

            if (_isDryRun)
            { Console.WriteLine(DryRunResult("go-online", new { device = input.DeviceName })); return 0; }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                try
                {
                    var device = FindDevice(project, input.DeviceName);
                    if (device == null) { Console.WriteLine(JsonError("Device not found")); return 1; }

                    var swContainer = device.GetService<SoftwareContainer>();
                    if (swContainer?.Software is PlcSoftware plc)
                    {
                        var online = plc.GetService("Siemens.Engineering.IOnlineProvider");
                        if (online != null)
                        {
                            online.GetType().GetMethod("GoOnline")?.Invoke(online, new object[] { });
                            Console.WriteLine(JsonOk(new { device = device.Name, online = true }));
                            return 0;
                        }
                    }
                    Console.WriteLine(JsonError("OnlineProvider not available"));
                    return 1;
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonError($"GoOnline failed: {ex.Message}"));
                    return 1;
                }
            }
        }

        static int GoOffline(string json)
        {
            var input = Json.Deserialize<DeviceInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            { Console.WriteLine(JsonError("Missing ProjectPath")); return 1; }

            if (_isDryRun)
            { Console.WriteLine(DryRunResult("go-offline", new { device = input.DeviceName })); return 0; }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                try
                {
                    var device = FindDevice(project, input.DeviceName);
                    if (device == null) { Console.WriteLine(JsonError("Device not found")); return 1; }

                    var swContainer = device.GetService<SoftwareContainer>();
                    if (swContainer?.Software is PlcSoftware plc)
                    {
                        var online = plc.GetService("Siemens.Engineering.IOnlineProvider");
                        if (online != null)
                        {
                            online.GetType().GetMethod("GoOffline")?.Invoke(online, new object[] { });
                            Console.WriteLine(JsonOk(new { device = device.Name, online = false }));
                            return 0;
                        }
                    }
                    Console.WriteLine(JsonError("OnlineProvider not available"));
                    return 1;
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonError($"GoOffline failed: {ex.Message}"));
                    return 1;
                }
            }
        }

        // ── P2-6: 硬件配置工具 ──

        static int GetDeviceConfig(string json)
        {
            var input = Json.Deserialize<DeviceInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            { Console.WriteLine(JsonError("Missing ProjectPath")); return 1; }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                try
                {
                    var devices = project.Devices;
                    var result = new List<object>();
                    foreach (var dev in devices)
                    {
                        var items = new List<object>();
                        CollectDeviceItems(dev.DeviceItems, items, 0);
                        result.Add(new { name = dev.Name, type = dev.GetType().Name, items });
                    }
                    Console.WriteLine(JsonOk(new { deviceCount = result.Count, devices = result }));
                    return 0;
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonError($"GetDeviceConfig failed: {ex.Message}"));
                    return 1;
                }
            }
        }

        static int GetRackSlot(string json)
        {
            var input = Json.Deserialize<DeviceInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            { Console.WriteLine(JsonError("Missing ProjectPath")); return 1; }

            using (var tia = AttachOrCreate())
            {
                var project = GetOrOpenProject(tia, input.ProjectPath);
                try
                {
                    var result = new List<object>();
                    foreach (var dev in project.Devices)
                    {
                        var slots = new List<object>();
                        try
                        {
                            var deviceItems = dev.DeviceItems;
                            CollectSlots(deviceItems, slots, 0);
                        }
                        catch { /* skip */ }
                        result.Add(new { device = dev.Name, slots });
                    }
                    Console.WriteLine(JsonOk(new { deviceCount = result.Count, devices = result }));
                    return 0;
                }
                catch (Exception ex)
                {
                    Console.WriteLine(JsonError($"GetRackSlot failed: {ex.Message}"));
                    return 1;
                }
            }
        }

        static void CollectDeviceItems(DeviceItemCollection items, List<object> result, int depth)
        {
            foreach (DeviceItem item in items)
            {
                var entry = new Dictionary<string, object>
                {
                    ["name"] = item.Name,
                    ["type"] = item.GetType().Name,
                    ["depth"] = depth,
                };
                try
                {
                    var children = new List<object>();
                    CollectDeviceItems(item.DeviceItems, children, depth + 1);
                    if (children.Count > 0) entry["children"] = children;
                }
                catch { /* leaf */ }
                result.Add(entry);
            }
        }

        static void CollectSlots(DeviceItemCollection items, List<object> result, int depth)
        {
            foreach (DeviceItem item in items)
            {
                var entry = new Dictionary<string, object>
                {
                    ["name"] = item.Name,
                    ["type"] = item.GetType().Name,
                    ["depth"] = depth,
                };
                try
                {
                    var children = new List<object>();
                    CollectSlots(item.DeviceItems, children, depth + 1);
                    if (children.Count > 0) entry["children"] = children;
                }
                catch { /* leaf */ }
                result.Add(entry);
            }
        }

        // ── 自动备份 ──

        static void AutoBackupProject(Project project)
        {
            if (!_isAutoBackup) return;

            try
            {
                var projDir = new FileInfo(project.Path).Directory;
                if (projDir == null) return;
                var parent = projDir.Parent;
                if (parent == null) return;

                var backupRoot = string.IsNullOrEmpty(_backupDir)
                    ? Path.Combine(parent.FullName, "backups")
                    : _backupDir;
                Directory.CreateDirectory(backupRoot);

                var timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                var projName = projDir.Name;
                var destDir = Path.Combine(backupRoot, $"{projName}_{timestamp}");

                // 轻量级备份：复制项目目录（不生成 .zap 归档，速度快）
                CopyDirectory(projDir.FullName, destDir);

                // 清理旧备份：保留最近 5 份
                CleanOldBackups(backupRoot, projName, 5);

                if (IsDebugEnabled)
                    Console.Error.WriteLine($"[TiaWorker] Backup saved: {destDir}");
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[TiaWorker] Backup failed: {ex.Message}");
            }
        }

        static void CopyDirectory(string source, string dest)
        {
            Directory.CreateDirectory(dest);
            foreach (var file in Directory.GetFiles(source))
                File.Copy(file, Path.Combine(dest, Path.GetFileName(file)), true);
            foreach (var dir in Directory.GetDirectories(source))
                CopyDirectory(dir, Path.Combine(dest, Path.GetFileName(dir)));
        }

        static void CleanOldBackups(string backupRoot, string projName, int keepCount)
        {
            var dirs = Directory.GetDirectories(backupRoot, $"{projName}_*")
                .OrderByDescending(d => d)
                .ToList();
            foreach (var old in dirs.Skip(keepCount))
            {
                try { Directory.Delete(old, true); }
                catch { /* skip locked dirs */ }
            }
        }

        static int ListBackups(string json)
        {
            var input = Json.Deserialize<ProjectInput>(json);
            if (string.IsNullOrEmpty(input?.ProjectPath))
            { Console.WriteLine(JsonError("Missing ProjectPath")); return 1; }

            try
            {
                var projDir = new FileInfo(input.ProjectPath).Directory;
                if (projDir?.Parent == null) { Console.WriteLine(JsonError("Cannot determine backup root")); return 1; }

                var backupRoot = string.IsNullOrEmpty(_backupDir)
                    ? Path.Combine(projDir.Parent.FullName, "backups")
                    : _backupDir;
                if (!Directory.Exists(backupRoot))
                { Console.WriteLine(JsonOk(new { backups = new List<object>() })); return 0; }

                var backups = Directory.GetDirectories(backupRoot, $"{projDir.Name}_*")
                    .Select(d => new
                    {
                        path = d,
                        name = Path.GetFileName(d),
                        created = Directory.GetCreationTime(d).ToString("yyyy-MM-dd HH:mm:ss")
                    })
                    .OrderByDescending(b => b.created)
                    .ToList();

                Console.WriteLine(JsonOk(new { count = backups.Count, backups }));
                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine(JsonError($"ListBackups failed: {ex.Message}"));
                return 1;
            }
        }

        // ── JSON 响应 ──

        static string JsonOk(object data) =>
            Json.Serialize(new { ok = true, result = data, error = (string)null });

        static string JsonError(string msg) =>
            Json.Serialize(new { ok = false, result = (object)null, error = msg });

        /// <summary>
        /// 在 dry-run 模式下返回预览，不执行实际修改。
        /// </summary>
        static string DryRunResult(string action, object previewData) =>
            JsonOk(new { dryRun = true, action, preview = previewData });
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

    class TagTableInput : ProjectInput
    {
        public string TagTableName { get; set; }
    }

    class AddTagInput : TagTableInput
    {
        public string TagName { get; set; }
        public string DataType { get; set; }
        public string LogicalAddress { get; set; }
    }

    class DeleteTagInput : TagTableInput
    {
        public string TagName { get; set; }
    }

    class SearchTagInput : ProjectInput
    {
        public string Query { get; set; }
    }

    class BlockNameInput : ProjectInput
    {
        public string BlockName { get; set; }
    }

    class CreateDbInput : ProjectInput
    {
        public string DbName { get; set; }
        public int DbNumber { get; set; }
    }

    class CreateProjectInput
    {
        public string ProjectName { get; set; }
        public string ParentDirectory { get; set; }
    }

    class ArchiveProjectInput : ProjectInput
    {
        public string OutputDir { get; set; }
        public string ArchiveName { get; set; }
    }

    class ExportAllInput : ProjectInput
    {
        public string OutputDir { get; set; }
    }

    class CloseProjectInput : ProjectInput
    {
        public bool Save { get; set; }
    }

    class UdtInput : ProjectInput
    {
        public string UdtName { get; set; }
    }

    class WatchTableInput : ProjectInput
    {
        public string WatchTableName { get; set; }
    }

    class ExportTagsInput : ProjectInput
    {
        public string OutputPath { get; set; }
    }

    class FindFreeAddressInput : ProjectInput
    {
        public string Area { get; set; }
        public int StartByte { get; set; }
    }

    class DeviceInput : ProjectInput
    {
        public string DeviceName { get; set; }
    }
}
