using Xunit;
using FluentAssertions;
using System.Text.Json;

namespace TiaWorker.Tests
{
    public class DtoSerializationTests
    {
        private static readonly JsonSerializerOptions Options = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            PropertyNameCaseInsensitive = true
        };

        // ── ProjectInput ──

        [Fact]
        public void ProjectInput_Serialization_RoundTrip()
        {
            var json = @"{""projectPath"":""D:\\TIA\\MyProject.ap17""}";
            var deserialized = JsonSerializer.Deserialize<ProjectInput>(json, Options);

            deserialized.Should().NotBeNull();
            deserialized!.ProjectPath.Should().Be(@"D:\TIA\MyProject.ap17");
        }

        [Fact]
        public void ProjectInput_EmptyPath_Deserializes()
        {
            var json = @"{""projectPath"":""""}";
            var deserialized = JsonSerializer.Deserialize<ProjectInput>(json, Options);

            deserialized!.ProjectPath.Should().Be("");
        }

        [Fact]
        public void ProjectInput_NullPath_Deserializes()
        {
            var json = "{}";
            var deserialized = JsonSerializer.Deserialize<ProjectInput>(json, Options);

            deserialized!.ProjectPath.Should().BeNull();
        }

        // ── ImportSclInput ──

        [Fact]
        public void ImportSclInput_Serialization_RoundTrip()
        {
            var json = @"{""projectPath"":""D:\\TIA\\MyProject.ap17"",""sclFilePath"":""D:\\TIA\\code.scl""}";
            var deserialized = JsonSerializer.Deserialize<ImportSclInput>(json, Options);

            deserialized!.ProjectPath.Should().Be(@"D:\TIA\MyProject.ap17");
            deserialized.SclFilePath.Should().Be(@"D:\TIA\code.scl");
        }

        [Fact]
        public void ImportSclInput_MissingSclFile_IsValidState()
        {
            var json = @"{""projectPath"":""D:\\TIA\\MyProject.ap17""}";
            var deserialized = JsonSerializer.Deserialize<ImportSclInput>(json, Options);

            deserialized!.ProjectPath.Should().NotBeNull();
            deserialized.SclFilePath.Should().BeNull();
        }

        // ── DownloadInput ──

        [Fact]
        public void DownloadInput_AllFields_RoundTrip()
        {
            var json = @"{""projectPath"":""test"",""deviceName"":""PLC_1"",""interfaceName"":""PN/IE_1"",""targetIp"":""192.168.0.1"",""timeoutSec"":120}";
            var deserialized = JsonSerializer.Deserialize<DownloadInput>(json, Options);

            deserialized!.ProjectPath.Should().Be("test");
            deserialized.DeviceName.Should().Be("PLC_1");
            deserialized.InterfaceName.Should().Be("PN/IE_1");
            deserialized.TargetIp.Should().Be("192.168.0.1");
            deserialized.TimeoutSec.Should().Be(120);
        }

        [Fact]
        public void DownloadInput_ZeroTimeout_Default()
        {
            var json = @"{""projectPath"":""test"",""timeoutSec"":0}";
            var deserialized = JsonSerializer.Deserialize<DownloadInput>(json, Options);

            deserialized!.TimeoutSec.Should().Be(0);
        }

        // ── CreateBlockInput ──

        [Fact]
        public void CreateBlockInput_AllFields_RoundTrip()
        {
            var json = @"{""projectPath"":""test"",""blockName"":""TestFB"",""blockNumber"":10,""blockType"":""FB"",""language"":""SCL""}";
            var deserialized = JsonSerializer.Deserialize<CreateBlockInput>(json, Options);

            deserialized!.BlockName.Should().Be("TestFB");
            deserialized.BlockNumber.Should().Be(10);
            deserialized.BlockType.Should().Be("FB");
            deserialized.Language.Should().Be("SCL");
        }

        [Fact]
        public void CreateBlockInput_ZeroBlockNumber_Allowed()
        {
            var json = @"{""blockName"":""OB1"",""blockNumber"":0}";
            var deserialized = JsonSerializer.Deserialize<CreateBlockInput>(json, Options);

            deserialized!.BlockNumber.Should().Be(0);
        }

        // ── AddTagInput ──

        [Fact]
        public void AddTagInput_AllFields_RoundTrip()
        {
            var json = @"{""projectPath"":""test"",""tagTableName"":""TagTable_1"",""tagName"":""Motor_Run"",""dataType"":""Bool"",""logicalAddress"":""M0.0""}";
            var deserialized = JsonSerializer.Deserialize<AddTagInput>(json, Options);

            deserialized!.TagTableName.Should().Be("TagTable_1");
            deserialized.TagName.Should().Be("Motor_Run");
            deserialized.DataType.Should().Be("Bool");
            deserialized.LogicalAddress.Should().Be("M0.0");
        }

        // ── CloseProjectInput ──

        [Fact]
        public void CloseProjectInput_SaveTrue_RoundTrip()
        {
            var json = @"{""projectPath"":""test"",""save"":true}";
            var deserialized = JsonSerializer.Deserialize<CloseProjectInput>(json, Options);

            deserialized!.Save.Should().BeTrue();
        }

        [Fact]
        public void CloseProjectInput_SaveFalse_RoundTrip()
        {
            var json = @"{""projectPath"":""test"",""save"":false}";
            var deserialized = JsonSerializer.Deserialize<CloseProjectInput>(json, Options);

            deserialized!.Save.Should().BeFalse();
        }

        // ── CreateProjectInput ──

        [Fact]
        public void CreateProjectInput_AllFields_RoundTrip()
        {
            var json = @"{""projectName"":""NewProject"",""parentDirectory"":""D:\\TIA\\Projects""}";
            var deserialized = JsonSerializer.Deserialize<CreateProjectInput>(json, Options);

            deserialized!.ProjectName.Should().Be("NewProject");
            deserialized.ParentDirectory.Should().Be(@"D:\TIA\Projects");
        }

        // ── FindFreeAddressInput ──

        [Fact]
        public void FindFreeAddressInput_AllFields_RoundTrip()
        {
            var json = @"{""projectPath"":""test"",""area"":""M"",""startByte"":100}";
            var deserialized = JsonSerializer.Deserialize<FindFreeAddressInput>(json, Options);

            deserialized!.Area.Should().Be("M");
            deserialized.StartByte.Should().Be(100);
        }

        // ── Inheritance chains ──

        [Fact]
        public void AddTagInput_IsTagTableInput_IsProjectInput()
        {
            var json = @"{""projectPath"":""p"",""tagTableName"":""t"",""tagName"":""n""}";
            var input = JsonSerializer.Deserialize<AddTagInput>(json, Options);

            input.Should().BeAssignableTo<ProjectInput>();
            input.Should().BeAssignableTo<TagTableInput>();
        }

        [Fact]
        public void SearchTagInput_HasQueryField()
        {
            var json = @"{""projectPath"":""p"",""query"":""Motor*""}";
            var deserialized = JsonSerializer.Deserialize<SearchTagInput>(json, Options);

            deserialized!.Query.Should().Be("Motor*");
        }
    }
}