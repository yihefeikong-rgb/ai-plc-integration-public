#nullable enable
// CartGen — JSON 驱动的 SimaticML LAD 生成器
// 用法: CartGen.exe <input.json> [output.xml]

using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Globalization;
using SimaticML.API;
using SimaticML.Blocks.FlagNet;
using SimaticML.Blocks.FlagNet.nPart;
using SimaticML.Blocks;
using SimaticML.Enums;

namespace CartGen;

class Program
{
    static int Main(string[] args)
    {
        if (args.Length < 1)
        {
            Console.Error.WriteLine("用法: CartGen.exe <input.json> [output.xml]");
            return 1;
        }

        var jsonPath = args[0];
        if (!File.Exists(jsonPath))
        {
            Console.Error.WriteLine($"文件不存在: {jsonPath}");
            return 1;
        }

        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
        var spec = JsonSerializer.Deserialize<LadderSpec>(File.ReadAllText(jsonPath), options)
            ?? throw new InvalidDataException("LadderSpec 不能为空");
        var outputPath = args.Length > 1 ? args[1] : Path.ChangeExtension(jsonPath, ".xml");
        ValidateSpec(spec);

        var fb = new BlockFB();
        fb.Init();
        var attr = fb.AttributeList;
        attr.BlockName = spec.BlockName;
        attr.BlockNumber = (uint)spec.BlockNumber;
        attr.ProgrammingLanguage = SimaticProgrammingLanguage.LADDER;

        var varMap = new Dictionary<string, SimaticVariable>();

        if (spec.Interface?.Inputs != null)
            foreach (var v in spec.Interface.Inputs)
                varMap[v.Name] = attr.INPUT.AddVariable(v.Name, ToDataType(v.Type));

        if (spec.Interface?.Outputs != null)
            foreach (var v in spec.Interface.Outputs)
                varMap[v.Name] = attr.OUTPUT.AddVariable(v.Name, ToDataType(v.Type));

        if (spec.Interface?.Local != null)
            foreach (var v in spec.Interface.Local)
                varMap[v.Name] = attr.STATIC.AddVariable(v.Name, ToDataType(v.Type));

        int netCount = 0;
        if (spec.Networks != null)
        {
            foreach (var net in spec.Networks)
            {
                var segment = new SimaticLADSegment();
                if (!string.IsNullOrEmpty(net.Title))
                    segment.Title[CultureInfo.CurrentCulture] = net.Title;
                if (!string.IsNullOrEmpty(net.Comment))
                    segment.Comment[CultureInfo.CurrentCulture] = net.Comment;

                SimaticPart? chain = null;
                if (net.Elements != null)
                    foreach (var elem in net.Elements)
                    {
                        var part = CreatePart(elem, varMap);
                        if (part != null) chain = (chain == null) ? part : (chain & part);
                    }

                // 注意：parallelElements 当前不可用
                // SimaticML OrPart 从 Powerrail 起始分支，不自持并联需电路中部汇合
                // 改用 Set/Reset 模式实现自保持

                if (chain == null)
                    throw new InvalidDataException($"网络 '{net.Title ?? "(未命名)"}' 没有可生成的 LAD 元件");
                var _ = segment.Powerrail & chain;
                segment.Create(fb);
                netCount++;
            }
        }

        var xmlDoc = SimaticMLAPI.CreateDocument(fb);
        xmlDoc.Save(outputPath);
        var manifestPath = WriteIoMappingManifest(spec, outputPath);
        Console.Error.WriteLine($"✅ {spec.BlockName}: {netCount} nets → {outputPath} ({new FileInfo(outputPath).Length} bytes), I/O mapping → {manifestPath}");
        return 0;
    }

    static SimaticPart? CreatePart(ElementSpec elem, Dictionary<string, SimaticVariable> varMap)
    {
        // Timer elements don't require an operand in varMap.
        if (elem.Type == "timer_on_delay" || elem.Type == "timer_off_delay")
        {
            if (string.IsNullOrWhiteSpace(elem.TimerInstance) || string.IsNullOrWhiteSpace(elem.PresetTime))
                throw new InvalidDataException("定时器缺少 timer_instance 或 preset_time");
            if (!string.IsNullOrEmpty(elem.Operand))
                throw new InvalidDataException("定时器不得携带会被忽略的 operand");
            var partType = elem.Type == "timer_on_delay" ? PartType.TON : PartType.TOF;
            return new TimerPart(partType)
            {
                InstanceAddress = elem.TimerInstance,
                InstanceScope = SimaticVariableScope.GLOBAL_VARIABLE,
                PT = CreateTimeLiteral(elem.PresetTime),
            };
        }

        if (string.IsNullOrEmpty(elem.Operand) || !varMap.TryGetValue(elem.Operand, out var var))
            throw new InvalidDataException($"引用了未声明变量: {elem.Operand ?? "(空)"}");
        return elem.Type switch
        {
            "normally_open" => new ContactPart() { Operand = var, Negated = false },
            "normally_closed" => new ContactPart() { Operand = var, Negated = true },
            "coil" => new CoilPart() { Operand = var },
            "coil_set" => new SetCoilPart() { Operand = var },
            "coil_reset" => new ResetCoilPart() { Operand = var },
            _ => throw new InvalidDataException($"不支持的 LAD 元件类型: {elem.Type}"),
        };
    }

    static SimaticVariable? CreateTimeLiteral(string? timeExpr)
    {
        if (string.IsNullOrEmpty(timeExpr))
            throw new InvalidDataException("定时器缺少 preset_time");
        return new SimaticLiteralConstant(SimaticDataType.TIMER, timeExpr);
    }

    static SimaticDataType ToDataType(string t) => (t?.ToUpper()) switch
    {
        "BOOL" or "BOOLEAN" => SimaticDataType.BOOLEAN,
        "INT" => SimaticDataType.INT, "REAL" => SimaticDataType.REAL,
        "WORD" => SimaticDataType.WORD,
        _ => throw new InvalidDataException($"不支持的数据类型: {t}"),
    };

    static void ValidateSpec(LadderSpec spec)
    {
        if (string.IsNullOrWhiteSpace(spec.BlockName) || spec.BlockNumber < 1)
            throw new InvalidDataException("LadderSpec 缺少有效 blockName 或 blockNumber");
        if (spec.Interface?.Inputs == null || spec.Interface.Outputs == null)
            throw new InvalidDataException("LadderSpec 缺少 inputs 或 outputs 接口");
        if (spec.Networks == null || spec.Networks.Count == 0)
            throw new InvalidDataException("LadderSpec 缺少 networks");

        var variables = new Dictionary<string, VariableSpec>(StringComparer.Ordinal);
        var outputNames = new HashSet<string>(StringComparer.Ordinal);
        AddVariables(spec.Interface.Inputs, variables, requireAddress: true, outputNames: null);
        AddVariables(spec.Interface.Outputs, variables, requireAddress: true, outputNames: outputNames);
        AddVariables(spec.Interface.Local ?? new List<VariableSpec>(), variables, requireAddress: false, outputNames: null);

        var timerInstances = new HashSet<string>(StringComparer.Ordinal);
        foreach (var network in spec.Networks)
        {
            if (network.Elements == null || network.Elements.Count == 0)
                throw new InvalidDataException($"网络 '{network.Title ?? "(未命名)"}' 缺少 elements");
            foreach (var element in network.Elements)
            {
                if (element.Type == "timer_on_delay" || element.Type == "timer_off_delay")
                {
                    if (string.IsNullOrWhiteSpace(element.TimerInstance) || string.IsNullOrWhiteSpace(element.PresetTime))
                        throw new InvalidDataException("定时器缺少 timer_instance 或 preset_time");
                    if (!timerInstances.Add(element.TimerInstance))
                        throw new InvalidDataException($"定时器实例重复: {element.TimerInstance}");
                    if (!string.IsNullOrEmpty(element.Operand))
                        throw new InvalidDataException("定时器不得携带会被忽略的 operand");
                    continue;
                }

                if (element.Type is not ("normally_open" or "normally_closed" or "coil" or "coil_set" or "coil_reset"))
                    throw new InvalidDataException($"不支持的 LAD 元件类型: {element.Type}");
                if (string.IsNullOrWhiteSpace(element.Operand) || !variables.TryGetValue(element.Operand, out var variable))
                    throw new InvalidDataException($"引用了未声明变量: {element.Operand ?? "(空)"}");
                if (!string.Equals(variable.Type, "Bool", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException($"布尔 LAD 元件引用了非 Bool 变量: {element.Operand}");
                if (element.Type is "coil" or "coil_set" or "coil_reset")
                {
                    if (!outputNames.Contains(element.Operand))
                        throw new InvalidDataException($"线圈必须驱动 outputs 中声明的变量: {element.Operand}");
                }
            }
        }
    }

    static void AddVariables(
        IEnumerable<VariableSpec> source,
        Dictionary<string, VariableSpec> variables,
        bool requireAddress,
        HashSet<string>? outputNames)
    {
        foreach (var variable in source)
        {
            if (string.IsNullOrWhiteSpace(variable.Name))
                throw new InvalidDataException("接口变量缺少名称");
            if (requireAddress && string.IsNullOrWhiteSpace(variable.Address))
                throw new InvalidDataException($"I/O 变量缺少物理地址映射: {variable.Name}");
            _ = ToDataType(variable.Type);
            if (!variables.TryAdd(variable.Name, variable))
                throw new InvalidDataException($"接口变量名重复: {variable.Name}");
            outputNames?.Add(variable.Name);
        }
    }

    static string WriteIoMappingManifest(LadderSpec spec, string outputPath)
    {
        // FB 接口变量本身不等同于项目级物理 I/O 绑定；该清单保留经校验的映射，
        // 供后续标签表/OB1 映射步骤核对，禁止在生成链中静默丢弃地址。
        var interfaceSpec = spec.Interface!;
        var manifest = new
        {
            blockName = spec.BlockName,
            inputs = interfaceSpec.Inputs!.Select(variable => new
            {
                name = variable.Name,
                type = variable.Type,
                address = variable.Address,
            }).ToArray(),
            outputs = interfaceSpec.Outputs!.Select(variable => new
            {
                name = variable.Name,
                type = variable.Type,
                address = variable.Address,
            }).ToArray(),
        };
        var directory = Path.GetDirectoryName(outputPath) ?? string.Empty;
        var manifestPath = Path.Combine(directory, $"{Path.GetFileNameWithoutExtension(outputPath)}.io-map.json");
        File.WriteAllText(
            manifestPath,
            JsonSerializer.Serialize(manifest, new JsonSerializerOptions { WriteIndented = true }));
        return manifestPath;
    }
}

class LadderSpec { public string BlockName { get; set; } = "AutoGen"; public int BlockNumber { get; set; } = 100; public InterfaceSpec? Interface { get; set; } public List<NetworkSpec>? Networks { get; set; } }
class InterfaceSpec { public List<VariableSpec>? Inputs { get; set; } public List<VariableSpec>? Outputs { get; set; } public List<VariableSpec>? Local { get; set; } }
class VariableSpec { public string Name { get; set; } = ""; public string Type { get; set; } = "Bool"; public string? Address { get; set; } public string? Comment { get; set; } }
class NetworkSpec { public string? Title { get; set; } public string? Comment { get; set; } public List<ElementSpec>? Elements { get; set; } public List<ElementSpec>? ParallelElements { get; set; } }
class ElementSpec { public string Type { get; set; } = "normally_open"; public string? Operand { get; set; } public string? Symbol { get; set; } public string? TimerInstance { get; set; } public string? PresetTime { get; set; } }
