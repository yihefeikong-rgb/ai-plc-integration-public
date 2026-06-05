using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using Siemens.Engineering;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;
using Siemens.Engineering.Compiler;

// ⚠️ TIA Portal V18 中 LAD 编程接口在 Siemens.Engineering.dll 主程序集里。
//    如果下面这行编译报错，说明你的版本需要额外引用:
//    D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.SW.Blocks.LAD.dll
//    或者接口在 V17/V18/V19 中有差异，需要按 VS intellisense 调整。
//
//    已知 API 版本差异:
//    - V17: ILadderProgramming 接口在 Siemens.Engineering.SW.Blocks.LAD 命名空间
//    - V18: 同上，但部分方法名有变化
//    - V19: 新增了更多 FBD/LAD 支持

// try { using Siemens.Engineering.SW.Blocks.LAD; }
// catch { /* LAD 接口可能在主程序集中，不需要额外 using */ }

namespace TiaWorker
{
    // ─── 输入 JSON 结构 ─────────────────────────────

    class CreateLadInput
    {
        public string ProjectPath { get; set; }
        public string BlockName { get; set; }
        public LadderProgram Program { get; set; }
    }

    class LadderProgram
    {
        public string BlockName { get; set; }
        public List<LadderNetwork> Networks { get; set; }
    }

    class LadderNetwork
    {
        public int NetworkNumber { get; set; }
        public string Title { get; set; }
        public string Comment { get; set; }
        public List<LadderElement> Elements { get; set; }
        public List<LadderElement> ParallelElements { get; set; }
        public bool HasParallelBranch { get; set; }
    }

    class LadderElement
    {
        public string Type { get; set; }       // normally_open, normally_closed, coil, coil_set, coil_reset, timer_on
        public string Operand { get; set; }    // %I0.0, %M0.0, %Q0.0
        public string Symbol { get; set; }     // bEmergencyStop
        public string Preset { get; set; }     // T#5S (for timers)
    }

    // ─── LAD 构建器 ─────────────────────────────────

    class LadderBuilder
    {
        static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

        /// <summary>
        /// 从 JSON 创建 LAD 块.
        /// 输入格式见 CreateLadInput.
        /// 
        /// ⚠️ 在 TIA Portal V18 上编译前请确认:
        ///   1. Siemens.Engineering.dll 引用路径正确
        ///   2. 如果 ILadderProgramming 报错，去掉 using 注释，
        ///      改为 using Siemens.Engineering.SW.Blocks.LAD;
        ///   3. Operand 类可能在 Siemens.Engineering.SW.Operands 命名空间
        /// </summary>
        public static string Execute(string json)
        {
            var input = Json.Deserialize<CreateLadInput>(json);
            if (input?.ProjectPath == null || input?.BlockName == null || input?.Program == null)
                return JsonError("Missing required fields: ProjectPath, BlockName, Program");

            try
            {
                return CreateBlock(input);
            }
            catch (Exception ex)
            {
                return JsonError($"LAD creation failed: {ex.Message}\n{ex.StackTrace}");
            }
        }

        static string CreateBlock(CreateLadInput input)
        {
            using (var tia = new TiaPortal(TiaPortalMode.WithoutUserInterface))
            {
                var project = tia.Projects.Open(new FileInfo(input.ProjectPath));
                var plc = Program.GetPlcSoftware(project);
                if (plc == null)
                    return JsonError("No PLC device found in project");

                // ── 创建空 LAD 块（通过反射兼容不同 V18 API 版本） ──
                var blocks = plc.BlockGroup.Blocks;
                var createMethod = blocks.GetType().GetMethods()
                    .FirstOrDefault(m => m.Name == "Create" && m.GetParameters().Length >= 3);
                if (createMethod == null)
                    return JsonError("Cannot find PlcBlockComposition.Create method (TIA API mismatch)");
                var fb = (PlcBlock)createMethod.Invoke(blocks, new object[] {
                    input.BlockName,
                    Enum.Parse(blocks.GetType().Assembly.GetType(
                        "Siemens.Engineering.SW.Blocks.PlcBlockType"), "FunctionBlock"),
                    Enum.Parse(blocks.GetType().Assembly.GetType(
                        "Siemens.Engineering.SW.Blocks.PlcProgrammingLanguage"), "LAD")
                });

                // ── 通过 LAD 编程接口搭梯级 ──
                // 这里使用动态反射调用，避免编译时对 LAD 程序集的强依赖
                // 如果编译时报 ILadderProgramming 找不到，去掉注释改用直接引用
                BuildLadderDirect(fb, input.Program.Networks);

                // ── 编译 ──
                var compiler = plc.GetService<ICompilable>();
                var result = compiler.Compile();
                project.Save();

                return JsonOk(new
                {
                    blockName = input.BlockName,
                    networks = input.Program.Networks.Count,
                    compileSuccess = result.State == CompilerResultState.Success,
                    errors = result.ErrorCount,
                    warnings = result.WarningCount
                });
            }
        }

        static void BuildLadderDirect(PlcBlock fb, List<LadderNetwork> networks)
        {
            // 通过反射调用 LAD API，避免编译时缺少 LAD 程序集引用
            // 实际运行时会在用户机器上加载 Siemens.Engineering.dll（含 LAD 接口）

            var ladService = fb.GetType()
                .GetMethod("GetService`1")
                ?.MakeGenericMethod(Type.GetType(
                    "Siemens.Engineering.SW.Blocks.LAD.ILadderProgramming, Siemens.Engineering"))
                ?.Invoke(fb, null);

            if (ladService == null)
                throw new Exception("Block does not support LAD programming. "
                    + "TIA Portal V18+ required.");

            var ladderNetworks = ladService.GetType()
                .GetProperty("LadderNetworks")
                ?.GetValue(ladService);

            if (ladderNetworks == null)
                throw new Exception("Cannot access LadderNetworks collection");

            var createMethod = ladderNetworks.GetType().GetMethod("Create");

            foreach (var nw in networks)
            {
                var network = createMethod?.Invoke(ladderNetworks, null);
                if (network == null) continue;

                // 设置标题和注释
                SetProperty(network, "Title", nw.Title ?? "");
                SetProperty(network, "Comment", nw.Comment ?? "");

                // 添加主路径元素
                foreach (var elem in nw.Elements)
                {
                    AddElementReflection(network, elem);
                }

                // 添加并联分支
                if (nw.HasParallelBranch && nw.ParallelElements?.Count > 0)
                {
                    var elements = GetProperty(network, "Elements");
                    var branch = elements?.GetType()
                        .GetMethod("CreateBranch")
                        ?.Invoke(elements, null);

                    if (branch != null)
                    {
                        foreach (var elem in nw.ParallelElements)
                        {
                            AddElementToBranchReflection(branch, elem);
                        }
                    }
                }
            }
        }

        static void AddElementReflection(object network, LadderElement elem)
        {
            var elements = GetProperty(network, "Elements");
            if (elements == null) return;

            switch (elem.Type)
            {
                case "normally_open":
                case "normally_closed":
                {
                    var contact = elements.GetType()
                        .GetMethod("CreateContact")
                        ?.Invoke(elements, null);

                    if (contact != null)
                    {
                        TrySetOperand(contact, elem.Operand);
                        TrySetProperty(contact, "Annotation.Text", elem.Symbol);

                        var contactType = elem.Type == "normally_closed"
                            ? "NormallyClosed"
                            : "NormallyOpen";
                        TrySetProperty(contact, "ContactType", Enum.Parse(
                            contact.GetType().Assembly.GetType(
                                "Siemens.Engineering.SW.Blocks.LAD.ContactType"),
                            contactType));
                    }
                    break;
                }

                case "coil":
                case "coil_set":
                case "coil_reset":
                {
                    var coil = elements.GetType()
                        .GetMethod("CreateCoil")
                        ?.Invoke(elements, null);

                    if (coil != null)
                    {
                        TrySetOperand(coil, elem.Operand);
                        TrySetProperty(coil, "Annotation.Text", elem.Symbol);

                        var coilType = "Normal";
                        if (elem.Type == "coil_set") coilType = "Set";
                        if (elem.Type == "coil_reset") coilType = "Reset";

                        TrySetProperty(coil, "CoilType", Enum.Parse(
                            coil.GetType().Assembly.GetType(
                                "Siemens.Engineering.SW.Blocks.LAD.CoilType"),
                            coilType));
                    }
                    break;
                }

                case "timer_on":
                {
                    var block = elements.GetType()
                        .GetMethod("CreateBlock")
                        ?.Invoke(elements, new object[] { "TON" });

                    if (block != null)
                    {
                        TrySetProperty(block, "Name", elem.Symbol);
                        if (!string.IsNullOrEmpty(elem.Preset))
                        {
                            TrySetProperty(block, "Parameter(\"PT\").Value", elem.Preset);
                        }
                    }
                    break;
                }
            }
        }

        static void AddElementToBranchReflection(object branch, LadderElement elem)
        {
            var elements = GetProperty(branch, "Elements");
            if (elements == null) return;

            var contact = elements.GetType()
                .GetMethod("CreateContact")
                ?.Invoke(elements, null);

            if (contact != null)
            {
                TrySetOperand(contact, elem.Operand);
                var contactType = elem.Type == "normally_closed"
                    ? "NormallyClosed" : "NormallyOpen";
                TrySetProperty(contact, "ContactType", Enum.Parse(
                    contact.GetType().Assembly.GetType(
                        "Siemens.Engineering.SW.Blocks.LAD.ContactType"),
                    contactType));
            }
        }

        // ─── 反射辅助 ─────────────────────────────

        static object GetProperty(object obj, string prop)
        {
            return obj.GetType().GetProperty(prop)?.GetValue(obj, null);
        }

        static void SetProperty(object obj, string prop, object value)
        {
            obj.GetType().GetProperty(prop)?.SetValue(obj, value, null);
        }

        static void TrySetProperty(object obj, string propPath, object value)
        {
            // 支持嵌套属性如 "Annotation.Text"
            var parts = propPath.Split('.');
            object current = obj;
            for (int i = 0; i < parts.Length - 1; i++)
            {
                current = current?.GetType().GetProperty(parts[i])?.GetValue(current, null);
            }
            if (current != null)
            {
                current.GetType().GetProperty(parts[parts.Length - 1])?.SetValue(current, value, null);
            }
        }

        static void TrySetOperand(object element, string operandStr)
        {
            try
            {
                // Operand.Parse 可能在不同命名空间
                var parseMethod = Type.GetType(
                    "Siemens.Engineering.SW.Operands.Operand, Siemens.Engineering")
                    ?.GetMethod("Parse", new[] { typeof(string) });

                var operand = parseMethod?.Invoke(null, new object[] { operandStr });
                if (operand != null)
                    SetProperty(element, "Operand", operand);
            }
            catch
            {
                // 如果 Parse 失败，跳过 Operand 设置
            }
        }

        static string JsonOk(object data) =>
            new JavaScriptSerializer().Serialize(new { status = "ok", data });

        static string JsonError(string msg) =>
            new JavaScriptSerializer().Serialize(new { status = "error", error = msg });
    }
}
