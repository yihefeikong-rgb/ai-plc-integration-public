using System;
using System.IO;
using System.Linq;
using System.Reflection;
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
                    case "list-devices":
                        return ListDevices(json);
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
                    Console.Error.WriteLine($"[TiaWorker] 可用模式: {string.Join(", ", connConfig.Modes.Select(m => m.Name))}");
                    foreach (var iface in mode.PcInterfaces)
                    {
                        Console.Error.WriteLine($"[TiaWorker]   接口: {iface.Name}");
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
                    Console.Error.WriteLine($"[TiaWorker] 设置下载目标为 PLCSIM Advanced...");

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
                                        Console.Error.WriteLine("[TiaWorker] ✅ TargetForSoftware = PlcSimulationAdvanced");
                                    }
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            Console.Error.WriteLine($"[TiaWorker] ⚠ 设置 TargetForSoftware 失败: {ex.Message}");
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
}
