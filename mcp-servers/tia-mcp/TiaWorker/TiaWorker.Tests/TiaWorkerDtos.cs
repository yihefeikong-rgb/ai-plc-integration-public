// TiaWorker 数据模型 — 镜像 Program.cs 中的 DTO 类
// ⚠️ 与 mcp-servers/tia-mcp/TiaWorker/Program.cs 保持同步
using System.Collections.Generic;

namespace TiaWorker
{
    public class ProjectInput
    {
        public string ProjectPath { get; set; }
    }

    public class ImportSclInput : ProjectInput
    {
        public string SclFilePath { get; set; }
    }

    public class DownloadInput : ProjectInput
    {
        public string DeviceName { get; set; }
        public string InterfaceName { get; set; }
        public string TargetIp { get; set; }
        public int TimeoutSec { get; set; }
    }

    public class CreateBlockInput : ProjectInput
    {
        public string BlockName { get; set; }
        public int BlockNumber { get; set; }
        public string BlockType { get; set; }
        public string Language { get; set; }
    }

    public class ExportBlockInput : ProjectInput
    {
        public string BlockName { get; set; }
        public string OutputPath { get; set; }
    }

    public class ImportBlockInput : ProjectInput
    {
        public string FilePath { get; set; }
        public bool Override { get; set; }
    }

    public class TagTableInput : ProjectInput
    {
        public string TagTableName { get; set; }
    }

    public class AddTagInput : TagTableInput
    {
        public string TagName { get; set; }
        public string DataType { get; set; }
        public string LogicalAddress { get; set; }
    }

    public class DeleteTagInput : TagTableInput
    {
        public string TagName { get; set; }
    }

    public class SearchTagInput : ProjectInput
    {
        public string Query { get; set; }
    }

    public class BlockNameInput : ProjectInput
    {
        public string BlockName { get; set; }
    }

    public class CreateDbInput : ProjectInput
    {
        public string DbName { get; set; }
        public int DbNumber { get; set; }
    }

    public class CreateProjectInput
    {
        public string ProjectName { get; set; }
        public string ParentDirectory { get; set; }
    }

    public class ArchiveProjectInput : ProjectInput
    {
        public string OutputDir { get; set; }
        public string ArchiveName { get; set; }
    }

    public class ExportAllInput : ProjectInput
    {
        public string OutputDir { get; set; }
    }

    public class CloseProjectInput : ProjectInput
    {
        public bool Save { get; set; }
    }

    public class UdtInput : ProjectInput
    {
        public string UdtName { get; set; }
    }

    public class WatchTableInput : ProjectInput
    {
        public string WatchTableName { get; set; }
    }

    public class ExportTagsInput : ProjectInput
    {
        public string OutputPath { get; set; }
    }

    public class FindFreeAddressInput : ProjectInput
    {
        public string Area { get; set; }
        public int StartByte { get; set; }
    }

    public class DeviceInput : ProjectInput
    {
        public string DeviceName { get; set; }
    }
}