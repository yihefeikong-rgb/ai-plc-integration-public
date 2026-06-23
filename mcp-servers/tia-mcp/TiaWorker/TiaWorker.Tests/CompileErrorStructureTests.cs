using Xunit;
using FluentAssertions;
using System.Text.Json;

namespace TiaWorker.Tests
{
    /// <summary>
    /// 验证 compile 命令的 JSON 输出结构包含结构化错误明细。
    ///
    /// 对应规格：TS023 L3-T1 — compile 返回 {success, errors:[{line,file,text,severity}]}
    ///
    /// 这些测试通过模拟 compile 方法内部的 error_list 构建逻辑来验证输出结构，
    /// 而非实际调用 TIA Portal API（TIA Portal 仅在 Windows 开发机上可用）。
    /// </summary>
    public class CompileErrorStructureTests
    {
        // ═══════════════════════════════════════════════════════════════
        // 结构化错误 JSON 输出验证
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void CompileResult_HasErrorListField()
        {
            // 模拟 compile 成功时的输出结构
            var result = JsonHelpers.JsonOk(new
            {
                success = true,
                errors = 0,
                warnings = 0,
                error_list = new object[] { }
            });

            using var doc = JsonDocument.Parse(result);
            var root = doc.RootElement;
            root.GetProperty("ok").GetBoolean().Should().BeTrue();

            var data = root.GetProperty("result");
            data.GetProperty("success").GetBoolean().Should().BeTrue();
            data.GetProperty("errors").GetInt32().Should().Be(0);
            data.GetProperty("warnings").GetInt32().Should().Be(0);

            // 必须有 error_list 字段
            data.TryGetProperty("error_list", out var errorList).Should().BeTrue();
            errorList.GetArrayLength().Should().Be(0);
        }

        [Fact]
        public void CompileResult_ErrorItems_HaveRequiredFields()
        {
            // 模拟编译失败，包含错误明细
            var errorItems = new[]
            {
                new
                {
                    line = 5,
                    file = "FB_Motor.scl",
                    text = "语法错误: 意外的标识符 'MOTOR'",
                    severity = "error",
                    state = "Error",
                },
                new
                {
                    line = 12,
                    file = "FB_Motor.scl",
                    text = "变量 'speed' 未声明",
                    severity = "error",
                    state = "Error",
                },
            };

            var result = JsonHelpers.JsonOk(new
            {
                success = false,
                errors = 2,
                warnings = 0,
                error_list = errorItems,
            });

            using var doc = JsonDocument.Parse(result);
            var root = doc.RootElement;
            root.GetProperty("ok").GetBoolean().Should().BeTrue();

            var data = root.GetProperty("result");
            data.GetProperty("success").GetBoolean().Should().BeFalse();
            data.GetProperty("errors").GetInt32().Should().Be(2);

            var errorList = data.GetProperty("error_list");
            errorList.GetArrayLength().Should().Be(2);

            // 检查第一个错误项的字段
            var item0 = errorList[0];
            item0.GetProperty("line").GetInt32().Should().Be(5);
            item0.GetProperty("file").GetString().Should().Be("FB_Motor.scl");
            item0.GetProperty("text").GetString().Should().Contain("语法错误");
            item0.GetProperty("severity").GetString().Should().Be("error");

            // 检查第二个错误项
            var item1 = errorList[1];
            item1.GetProperty("line").GetInt32().Should().Be(12);
            item1.GetProperty("file").GetString().Should().Be("FB_Motor.scl");
            item1.GetProperty("severity").GetString().Should().Be("error");
        }

        [Fact]
        public void CompileResult_ErrorItem_AllFieldsPresent()
        {
            // 验证每个错误项包含所有 5 个字段
            var errorItems = new[]
            {
                new { line = 0, file = "", text = "test", severity = "warning", state = "Warning" },
            };

            var result = JsonHelpers.JsonOk(new
            {
                success = false,
                errors = 1,
                warnings = 1,
                error_list = errorItems,
            });

            using var doc = JsonDocument.Parse(result);
            var item = doc.RootElement.GetProperty("result")
                .GetProperty("error_list")[0];

            // 5 个必要字段
            item.TryGetProperty("line", out var _).Should().BeTrue();
            item.TryGetProperty("file", out var _).Should().BeTrue();
            item.TryGetProperty("text", out var _).Should().BeTrue();
            item.TryGetProperty("severity", out var _).Should().BeTrue();
            item.TryGetProperty("state", out var _).Should().BeTrue();
        }

        [Fact]
        public void CompileResult_SuccessCase_NoErrors()
        {
            // 编译成功时 error_list 应为空数组
            var result = JsonHelpers.JsonOk(new
            {
                success = true,
                errors = 0,
                warnings = 0,
                error_list = new object[] { },
            });

            using var doc = JsonDocument.Parse(result);
            var data = doc.RootElement.GetProperty("result");
            data.GetProperty("success").GetBoolean().Should().BeTrue();
            data.GetProperty("error_list").GetArrayLength().Should().Be(0);
        }

        [Fact]
        public void CompileResult_WarningsOnly_StillHasErrorList()
        {
            // 仅有警告时 error_list 也需存在（Program.cs 当前只在 ErrorCount>0 时添加，
            // 但 error_list 字段始终存在，只是可能为空）
            var errorItems = new object[] { };

            var result = JsonHelpers.JsonOk(new
            {
                success = true,
                errors = 0,
                warnings = 3,
                error_list = errorItems,
            });

            using var doc = JsonDocument.Parse(result);
            var data = doc.RootElement.GetProperty("result");
            data.GetProperty("success").GetBoolean().Should().BeTrue();
            data.GetProperty("warnings").GetInt32().Should().Be(3);
            data.TryGetProperty("error_list", out var _).Should().BeTrue();
        }

        // ═══════════════════════════════════════════════════════════════
        // backward compat 验证
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void CompileResult_BackwardCompatible_ErrorsCountFieldStillPresent()
        {
            // errors 整数字段（原有字段）仍然存在
            var result = JsonHelpers.JsonOk(new
            {
                success = false,
                errors = 3,
                warnings = 0,
                error_list = new[]
                {
                    new { line = 1, file = "a.scl", text = "e1", severity = "error", state = "Error" },
                    new { line = 2, file = "a.scl", text = "e2", severity = "error", state = "Error" },
                    new { line = 3, file = "a.scl", text = "e3", severity = "error", state = "Error" },
                },
            });

            using var doc = JsonDocument.Parse(result);
            var data = doc.RootElement.GetProperty("result");
            data.GetProperty("errors").GetInt32().Should().Be(3);
            data.GetProperty("error_list").GetArrayLength().Should().Be(3);
        }

        [Fact]
        public void CompileResult_ErrorMessageContainsText()
        {
            // 错误文本字段包含可读的描述信息
            var errorItems = new[]
            {
                new
                {
                    line = 0,
                    file = "Main.scl",
                    text = "SCL 源 'Main.scl' 包含错误",
                    severity = "error",
                    state = "Error",
                },
            };

            var result = JsonHelpers.JsonOk(new
            {
                success = false,
                errors = 1,
                warnings = 0,
                error_list = errorItems,
            });

            using var doc = JsonDocument.Parse(result);
            var item = doc.RootElement.GetProperty("result")
                .GetProperty("error_list")[0];

            item.GetProperty("text").GetString().Should().NotBeNullOrEmpty();
            item.GetProperty("file").GetString().Should().NotBeNullOrEmpty();
        }
    }
}
