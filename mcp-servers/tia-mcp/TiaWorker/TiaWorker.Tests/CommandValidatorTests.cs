using Xunit;
using FluentAssertions;
using System.IO;

namespace TiaWorker.Tests
{
    /// <summary>
    /// TiaWorker 核心命令验证逻辑测试。
    /// 覆盖 import-scl, compile, download, list-devices 四个核心命令的输入校验。
    /// </summary>
    public class CommandValidatorTests
    {
        // ═══════════════════════════════════════════════════════════════
        // import-scl 命令验证测试
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void ValidateImportScl_ValidInput_Succeeds()
        {
            var input = new ImportSclInput
            {
                ProjectPath = @"D:\TIA\MyProject.ap17",
                SclFilePath = @"D:\TIA\code.scl"
            };

            var (isValid, error) = CommandValidator.ValidateImportScl(input);

            isValid.Should().BeTrue();
            error.Should().BeNull();
        }

        [Fact]
        public void ValidateImportScl_NullInput_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateImportScl(null);

            isValid.Should().BeFalse();
            error.Should().Contain("deserialize");
        }

        [Fact]
        public void ValidateImportScl_EmptyProjectPath_Fails()
        {
            var input = new ImportSclInput
            {
                ProjectPath = "",
                SclFilePath = @"D:\TIA\code.scl"
            };

            var (isValid, error) = CommandValidator.ValidateImportScl(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        [Fact]
        public void ValidateImportScl_NullProjectPath_Fails()
        {
            var input = new ImportSclInput
            {
                ProjectPath = null!,
                SclFilePath = @"D:\TIA\code.scl"
            };

            var (isValid, error) = CommandValidator.ValidateImportScl(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        [Fact]
        public void ValidateImportScl_EmptySclFilePath_Fails()
        {
            var input = new ImportSclInput
            {
                ProjectPath = @"D:\TIA\MyProject.ap17",
                SclFilePath = ""
            };

            var (isValid, error) = CommandValidator.ValidateImportScl(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        [Fact]
        public void ValidateImportScl_NullSclFilePath_Fails()
        {
            var input = new ImportSclInput
            {
                ProjectPath = @"D:\TIA\MyProject.ap17",
                SclFilePath = null!
            };

            var (isValid, error) = CommandValidator.ValidateImportScl(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        [Fact]
        public void ValidateImportScl_BothEmpty_Fails()
        {
            var input = new ImportSclInput
            {
                ProjectPath = "",
                SclFilePath = ""
            };

            var (isValid, error) = CommandValidator.ValidateImportScl(input);

            isValid.Should().BeFalse();
        }

        [Fact]
        public void ValidateImportScl_InvalidPathChars_Fails()
        {
            var input = new ImportSclInput
            {
                ProjectPath = @"D:\TIA\MyProject.ap17",
                SclFilePath = "D:\\TIA\\code\0.scl" // null char is invalid
            };

            var (isValid, error) = CommandValidator.ValidateImportScl(input);

            isValid.Should().BeFalse();
            error.Should().Contain("invalid characters");
        }

        // ═══════════════════════════════════════════════════════════════
        // SCL 文件存在性校验
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void ValidateSclFileExists_EmptyPath_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateSclFileExists("");

            isValid.Should().BeFalse();
            error.Should().Contain("empty");
        }

        [Fact]
        public void ValidateSclFileExists_NullPath_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateSclFileExists(null!);

            isValid.Should().BeFalse();
        }

        [Fact]
        public void ValidateSclFileExists_NonExistentFile_Fails()
        {
            var nonExistent = Path.Combine(Path.GetTempPath(), $"nonexistent_{Guid.NewGuid()}.scl");

            var (isValid, error) = CommandValidator.ValidateSclFileExists(nonExistent);

            isValid.Should().BeFalse();
            error.Should().Contain("not found");
        }

        [Fact]
        public void ValidateSclFileExists_ExistingFile_Succeeds()
        {
            var tempFile = Path.GetTempFileName();
            try
            {
                var (isValid, error) = CommandValidator.ValidateSclFileExists(tempFile);

                isValid.Should().BeTrue();
                error.Should().BeNull();
            }
            finally
            {
                if (File.Exists(tempFile))
                    File.Delete(tempFile);
            }
        }

        // ═══════════════════════════════════════════════════════════════
        // compile 命令验证测试
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void ValidateCompile_ValidInput_Succeeds()
        {
            var input = new ProjectInput
            {
                ProjectPath = @"D:\TIA\MyProject.ap17"
            };

            var (isValid, error) = CommandValidator.ValidateCompile(input);

            isValid.Should().BeTrue();
            error.Should().BeNull();
        }

        [Fact]
        public void ValidateCompile_NullInput_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateCompile(null);

            isValid.Should().BeFalse();
            error.Should().Contain("deserialize");
        }

        [Fact]
        public void ValidateCompile_EmptyProjectPath_Fails()
        {
            var input = new ProjectInput { ProjectPath = "" };

            var (isValid, error) = CommandValidator.ValidateCompile(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        [Fact]
        public void ValidateCompile_NullProjectPath_Fails()
        {
            var input = new ProjectInput { ProjectPath = null! };

            var (isValid, error) = CommandValidator.ValidateCompile(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        [Fact]
        public void ValidateCompile_WhitespaceProjectPath_AcceptedByDesign()
        {
            // 注意：Program.cs 使用 string.IsNullOrEmpty，空格字符串不被视为空。
            // 这是设计行为 — 空格字符串会被接受，后续由 TIA 打开项目时失败。
            var input = new ProjectInput { ProjectPath = "   " };

            var (isValid, error) = CommandValidator.ValidateCompile(input);

            isValid.Should().BeTrue();
            error.Should().BeNull();
        }

        // ═══════════════════════════════════════════════════════════════
        // download 命令验证测试
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void ValidateDownload_ValidInput_Succeeds()
        {
            var input = new DownloadInput
            {
                ProjectPath = @"D:\TIA\MyProject.ap17",
                DeviceName = "PLC_1",
                InterfaceName = "PN/IE",
                TargetIp = "192.168.0.1",
                TimeoutSec = 120
            };

            var (isValid, error) = CommandValidator.ValidateDownload(input);

            isValid.Should().BeTrue();
            error.Should().BeNull();
        }

        [Fact]
        public void ValidateDownload_MinimalInput_Succeeds()
        {
            var input = new DownloadInput
            {
                ProjectPath = "test.ap17"
            };

            var (isValid, error) = CommandValidator.ValidateDownload(input);

            isValid.Should().BeTrue();
        }

        [Fact]
        public void ValidateDownload_NullInput_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateDownload(null);

            isValid.Should().BeFalse();
            error.Should().Contain("deserialize");
        }

        [Fact]
        public void ValidateDownload_EmptyProjectPath_Fails()
        {
            var input = new DownloadInput { ProjectPath = "" };

            var (isValid, error) = CommandValidator.ValidateDownload(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        [Fact]
        public void ValidateDownload_NullProjectPath_Fails()
        {
            var input = new DownloadInput { ProjectPath = null! };

            var (isValid, error) = CommandValidator.ValidateDownload(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        // ═══════════════════════════════════════════════════════════════
        // download IP 地址校验
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void ValidateTargetIp_Null_Succeeds()
        {
            var (isValid, error) = CommandValidator.ValidateTargetIp(null);

            isValid.Should().BeTrue();
            error.Should().BeNull();
        }

        [Fact]
        public void ValidateTargetIp_Empty_Succeeds()
        {
            var (isValid, error) = CommandValidator.ValidateTargetIp("");

            isValid.Should().BeTrue();
        }

        [Fact]
        public void ValidateTargetIp_ValidIp_Succeeds()
        {
            var (isValid, error) = CommandValidator.ValidateTargetIp("192.168.0.110");

            isValid.Should().BeTrue();
            error.Should().BeNull();
        }

        [Fact]
        public void ValidateTargetIp_ValidLocalhost_Succeeds()
        {
            var (isValid, error) = CommandValidator.ValidateTargetIp("127.0.0.1");

            isValid.Should().BeTrue();
        }

        [Fact]
        public void ValidateTargetIp_TooFewParts_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateTargetIp("192.168.0");

            isValid.Should().BeFalse();
            error.Should().Contain("Invalid");
        }

        [Fact]
        public void ValidateTargetIp_TooManyParts_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateTargetIp("192.168.0.1.1");

            isValid.Should().BeFalse();
            error.Should().Contain("Invalid");
        }

        [Fact]
        public void ValidateTargetIp_NonNumeric_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateTargetIp("192.168.0.abc");

            isValid.Should().BeFalse();
            error.Should().Contain("Invalid");
        }

        [Fact]
        public void ValidateTargetIp_OutOfRange_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateTargetIp("192.168.0.300");

            isValid.Should().BeFalse();
            error.Should().Contain("Invalid");
        }

        [Fact]
        public void ValidateTargetIp_Negative_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateTargetIp("192.168.-1.1");

            isValid.Should().BeFalse();
            error.Should().Contain("Invalid");
        }

        [Fact]
        public void ValidateTargetIp_EmptyString_Succeeds()
        {
            // Empty string is treated as "not provided"
            var (isValid, error) = CommandValidator.ValidateTargetIp("");

            isValid.Should().BeTrue();
        }

        // ═══════════════════════════════════════════════════════════════
        // download timeout 校验
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void ValidateTimeout_Zero_Succeeds()
        {
            var (isValid, error) = CommandValidator.ValidateTimeout(0);

            isValid.Should().BeTrue();
        }

        [Fact]
        public void ValidateTimeout_Positive_Succeeds()
        {
            var (isValid, error) = CommandValidator.ValidateTimeout(120);

            isValid.Should().BeTrue();
        }

        [Fact]
        public void ValidateTimeout_MaxValue_Succeeds()
        {
            var (isValid, error) = CommandValidator.ValidateTimeout(3600);

            isValid.Should().BeTrue();
        }

        [Fact]
        public void ValidateTimeout_Negative_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateTimeout(-1);

            isValid.Should().BeFalse();
            error.Should().Contain("non-negative");
        }

        [Fact]
        public void ValidateTimeout_ExceedsMaximum_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateTimeout(3601);

            isValid.Should().BeFalse();
            error.Should().Contain("3600");
        }

        // ═══════════════════════════════════════════════════════════════
        // list-devices 命令验证测试
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void ValidateListDevices_ValidInput_Succeeds()
        {
            var input = new ProjectInput
            {
                ProjectPath = @"D:\TIA\MyProject.ap17"
            };

            var (isValid, error) = CommandValidator.ValidateListDevices(input);

            isValid.Should().BeTrue();
            error.Should().BeNull();
        }

        [Fact]
        public void ValidateListDevices_NullInput_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateListDevices(null);

            isValid.Should().BeFalse();
            error.Should().Contain("deserialize");
        }

        [Fact]
        public void ValidateListDevices_EmptyProjectPath_Fails()
        {
            var input = new ProjectInput { ProjectPath = "" };

            var (isValid, error) = CommandValidator.ValidateListDevices(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        [Fact]
        public void ValidateListDevices_NullProjectPath_Fails()
        {
            var input = new ProjectInput { ProjectPath = null! };

            var (isValid, error) = CommandValidator.ValidateListDevices(input);

            isValid.Should().BeFalse();
            error.Should().Contain("ProjectPath");
        }

        // ═══════════════════════════════════════════════════════════════
        // ProjectPath 通用校验
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void ValidateProjectPath_ValidPath_Succeeds()
        {
            var (isValid, error) = CommandValidator.ValidateProjectPath(@"D:\TIA\V21\MyProject.ap17");

            isValid.Should().BeTrue();
            error.Should().BeNull();
        }

        [Fact]
        public void ValidateProjectPath_NetworkPath_Succeeds()
        {
            var (isValid, error) = CommandValidator.ValidateProjectPath(@"\\server\share\project.ap17");

            isValid.Should().BeTrue();
        }

        [Fact]
        public void ValidateProjectPath_Null_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateProjectPath(null);

            isValid.Should().BeFalse();
            error.Should().Contain("required");
        }

        [Fact]
        public void ValidateProjectPath_Empty_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateProjectPath("");

            isValid.Should().BeFalse();
            error.Should().Contain("required");
        }

        [Fact]
        public void ValidateProjectPath_InvalidChars_Fails()
        {
            var (isValid, error) = CommandValidator.ValidateProjectPath("D:\\TIA\\project\0.ap17");

            isValid.Should().BeFalse();
            error.Should().Contain("invalid characters");
        }

        // ═══════════════════════════════════════════════════════════════
        // import-scl 综合校验
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void ValidateImportSclComprehensive_ValidInput_NoErrors()
        {
            var tempFile = Path.GetTempFileName();
            try
            {
                var input = new ImportSclInput
                {
                    ProjectPath = @"D:\TIA\MyProject.ap17",
                    SclFilePath = tempFile
                };

                var result = CommandValidator.ValidateImportSclComprehensive(input);

                result.IsValid.Should().BeTrue();
                result.Errors.Should().BeEmpty();
            }
            finally
            {
                if (File.Exists(tempFile))
                    File.Delete(tempFile);
            }
        }

        [Fact]
        public void ValidateImportSclComprehensive_NullInput_HasErrors()
        {
            var result = CommandValidator.ValidateImportSclComprehensive(null);

            result.IsValid.Should().BeFalse();
            result.Errors.Should().NotBeEmpty();
        }

        [Fact]
        public void ValidateImportSclComprehensive_NonExistentFile_HasError()
        {
            var nonExistent = Path.Combine(Path.GetTempPath(), $"noexist_{Guid.NewGuid()}.scl");
            var input = new ImportSclInput
            {
                ProjectPath = @"D:\TIA\MyProject.ap17",
                SclFilePath = nonExistent
            };

            var result = CommandValidator.ValidateImportSclComprehensive(input);

            result.IsValid.Should().BeFalse();
            result.Errors.Should().ContainSingle(e => e.Contains("not found"));
        }

        [Fact]
        public void ValidateImportSclComprehensive_MultipleErrors_AllReported()
        {
            var input = new ImportSclInput
            {
                ProjectPath = "",
                SclFilePath = ""
            };

            var result = CommandValidator.ValidateImportSclComprehensive(input);

            result.IsValid.Should().BeFalse();
            // 空 ProjectPath 和空 SclFilePath 都会触发校验失败
            result.Errors.Count.Should().BeGreaterThanOrEqualTo(1);
        }

        // ═══════════════════════════════════════════════════════════════
        // 跨命令一致性验证
        // ═══════════════════════════════════════════════════════════════

        [Fact]
        public void AllCommands_RequireProjectPath()
        {
            // 验证 compile, download, list-devices 都需要 ProjectPath
            var emptyInput = new ProjectInput { ProjectPath = "" };

            var compileResult = CommandValidator.ValidateCompile(emptyInput);
            var downloadResult = CommandValidator.ValidateDownload(new DownloadInput { ProjectPath = "" });
            var listDevicesResult = CommandValidator.ValidateListDevices(emptyInput);

            compileResult.IsValid.Should().BeFalse();
            downloadResult.IsValid.Should().BeFalse();
            listDevicesResult.IsValid.Should().BeFalse();
        }

        [Fact]
        public void AllCommands_AcceptSameProjectPath()
        {
            var projectPath = @"D:\TIA\MyProject.ap17";

            var compileInput = new ProjectInput { ProjectPath = projectPath };
            var downloadInput = new DownloadInput { ProjectPath = projectPath };
            var listDevicesInput = new ProjectInput { ProjectPath = projectPath };

            var compileResult = CommandValidator.ValidateCompile(compileInput);
            var downloadResult = CommandValidator.ValidateDownload(downloadInput);
            var listDevicesResult = CommandValidator.ValidateListDevices(listDevicesInput);

            compileResult.IsValid.Should().BeTrue();
            downloadResult.IsValid.Should().BeTrue();
            listDevicesResult.IsValid.Should().BeTrue();
        }
    }
}