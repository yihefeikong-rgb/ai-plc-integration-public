#nullable enable
// CartGen — JSON 驱动的 SimaticML LAD 生成器
// 用法: CartGen.exe <input.json> [output.xml]

using System;
using System.IO;
using System.Collections.Generic;
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
        var spec = JsonSerializer.Deserialize<LadderSpec>(File.ReadAllText(jsonPath), options);
        var outputPath = args.Length > 1 ? args[1] : Path.ChangeExtension(jsonPath, ".xml");

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

                if (chain != null) { var _ = segment.Powerrail & chain; segment.Create(fb); netCount++; }
            }
        }

        var xmlDoc = SimaticMLAPI.CreateDocument(fb);
        xmlDoc.Save(outputPath);
        Console.Error.WriteLine($"✅ {spec.BlockName}: {netCount} nets → {outputPath} ({new FileInfo(outputPath).Length} bytes)");
        return 0;
    }

    static SimaticPart? CreatePart(ElementSpec elem, Dictionary<string, SimaticVariable> varMap)
    {
        // Timer elements don't require an operand in varMap
        if (elem.Type == "timer_on_delay" || elem.Type == "timer_off_delay")
        {
            var partType = elem.Type == "timer_on_delay" ? PartType.TON : PartType.TOF;
            return new TimerPart(partType)
            {
                InstanceAddress = elem.TimerInstance,
                InstanceScope = SimaticVariableScope.GLOBAL_VARIABLE,
                PT = CreateTimeLiteral(elem.PresetTime),
            };
        }

        if (string.IsNullOrEmpty(elem.Operand) || !varMap.TryGetValue(elem.Operand, out var var)) return null;
        return elem.Type switch
        {
            "normally_open" => new ContactPart() { Operand = var, Negated = false },
            "normally_closed" => new ContactPart() { Operand = var, Negated = true },
            "coil" => new CoilPart() { Operand = var },
            "coil_set" => new SetCoilPart() { Operand = var },
            "coil_reset" => new ResetCoilPart() { Operand = var },
            _ => null,
        };
    }

    static SimaticVariable? CreateTimeLiteral(string? timeExpr)
    {
        if (string.IsNullOrEmpty(timeExpr)) return null;
        return new SimaticLiteralConstant(SimaticDataType.TIMER, timeExpr);
    }

    static SimaticDataType ToDataType(string t) => (t?.ToUpper()) switch
    {
        "BOOL" or "BOOLEAN" => SimaticDataType.BOOLEAN,
        "INT" => SimaticDataType.INT, "REAL" => SimaticDataType.REAL,
         "WORD" => SimaticDataType.WORD,
        _ => SimaticDataType.BOOLEAN,
    };
}

class LadderSpec { public string BlockName { get; set; } = "AutoGen"; public int BlockNumber { get; set; } = 100; public InterfaceSpec? Interface { get; set; } public List<NetworkSpec>? Networks { get; set; } }
class InterfaceSpec { public List<VariableSpec>? Inputs { get; set; } public List<VariableSpec>? Outputs { get; set; } public List<VariableSpec>? Local { get; set; } }
class VariableSpec { public string Name { get; set; } = ""; public string Type { get; set; } = "Bool"; public string? Comment { get; set; } }
class NetworkSpec { public string? Title { get; set; } public string? Comment { get; set; } public List<ElementSpec>? Elements { get; set; } public List<ElementSpec>? ParallelElements { get; set; } }
class ElementSpec { public string Type { get; set; } = "normally_open"; public string? Operand { get; set; } public string? Symbol { get; set; } public string? TimerInstance { get; set; } public string? PresetTime { get; set; } }
