// TiaWorker 命令验证逻辑 — 镜像 Program.cs 中核心命令的输入校验部分
// 提取可测试的验证逻辑，不依赖 Siemens.Engineering DLL
using System;
using System.IO;
using System.Collections.Generic;

namespace TiaWorker
{
    /// <summary>
    /// 封装核心命令的输入验证逻辑，返回 (isValid, errorMessage) 元组。
    /// 与 Program.cs 中的命令验证逻辑保持同步。
    /// </summary>
    public static class CommandValidator
    {
        /// <summary>
        /// 验证 import-scl 命令的输入参数。
        /// 对应 Program.cs ImportScl() 的 JSON 反序列化后校验部分。
        /// </summary>
        public static (bool IsValid, string? Error) ValidateImportScl(ImportSclInput? input)
        {
            if (input == null)
                return (false, "Failed to deserialize ImportSclInput");

            if (string.IsNullOrEmpty(input.ProjectPath))
                return (false, "Missing ProjectPath or SclFilePath");

            if (string.IsNullOrEmpty(input.SclFilePath))
                return (false, "Missing ProjectPath or SclFilePath");

            // SclFilePath 路径格式校验：路径中不应包含非法字符
            if (input.SclFilePath.IndexOfAny(Path.GetInvalidPathChars()) >= 0)
                return (false, "SCL file path contains invalid characters");

            return (true, null);
        }

        /// <summary>
        /// 验证 import-scl 的文件存在性（独立验证，因为需要文件系统访问）。
        /// 对应 Program.cs ImportScl() 中 sclFile.Exists 检查。
        /// </summary>
        public static (bool IsValid, string? Error) ValidateSclFileExists(string sclFilePath)
        {
            if (string.IsNullOrEmpty(sclFilePath))
                return (false, "SCL file path is empty");

            if (!File.Exists(sclFilePath))
                return (false, $"SCL file not found: {sclFilePath}");

            return (true, null);
        }

        /// <summary>
        /// 验证 compile 命令的输入参数。
        /// 对应 Program.cs Compile() 的 JSON 反序列化后校验部分。
        /// </summary>
        public static (bool IsValid, string? Error) ValidateCompile(ProjectInput? input)
        {
            if (input == null)
                return (false, "Failed to deserialize ProjectInput");

            if (string.IsNullOrEmpty(input.ProjectPath))
                return (false, "Missing ProjectPath");

            return (true, null);
        }

        /// <summary>
        /// 验证 download 命令的输入参数。
        /// 对应 Program.cs Download() 的 JSON 反序列化后校验部分。
        /// </summary>
        public static (bool IsValid, string? Error) ValidateDownload(DownloadInput? input)
        {
            if (input == null)
                return (false, "Failed to deserialize DownloadInput");

            if (string.IsNullOrEmpty(input.ProjectPath))
                return (false, "Missing ProjectPath");

            return (true, null);
        }

        /// <summary>
        /// 验证 download 的 IP 地址格式（可选参数，如果提供则校验）。
        /// </summary>
        public static (bool IsValid, string? Error) ValidateTargetIp(string? targetIp)
        {
            if (string.IsNullOrEmpty(targetIp))
                return (true, null); // IP 是可选的

            // 简单格式校验：至少包含 3 个点，每个部分都是数字
            var parts = targetIp.Split('.');
            if (parts.Length != 4)
                return (false, $"Invalid IP address format: {targetIp}");

            foreach (var part in parts)
            {
                if (!int.TryParse(part, out var num) || num < 0 || num > 255)
                    return (false, $"Invalid IP address component: {part}");
            }

            return (true, null);
        }

        /// <summary>
        /// 验证 download 的 timeout 参数。
        /// </summary>
        public static (bool IsValid, string? Error) ValidateTimeout(int timeoutSec)
        {
            if (timeoutSec < 0)
                return (false, "Timeout must be non-negative");

            if (timeoutSec > 3600)
                return (false, "Timeout must not exceed 3600 seconds");

            return (true, null);
        }

        /// <summary>
        /// 验证 list-devices 命令的输入参数。
        /// 对应 Program.cs ListDevices() 的 JSON 反序列化后校验部分。
        /// </summary>
        public static (bool IsValid, string? Error) ValidateListDevices(ProjectInput? input)
        {
            if (input == null)
                return (false, "Failed to deserialize ProjectInput");

            if (string.IsNullOrEmpty(input.ProjectPath))
                return (false, "Missing ProjectPath");

            return (true, null);
        }

        /// <summary>
        /// 验证 projectPath 是否为有效的文件路径格式。
        /// 可用于所有需要 ProjectPath 的命令。
        /// </summary>
        public static (bool IsValid, string? Error) ValidateProjectPath(string? projectPath)
        {
            if (string.IsNullOrEmpty(projectPath))
                return (false, "ProjectPath is required");

            if (projectPath.IndexOfAny(Path.GetInvalidPathChars()) >= 0)
                return (false, "ProjectPath contains invalid characters");

            return (true, null);
        }

        /// <summary>
        /// 提取 import-scl 命令所需的所有校验结果。
        /// 一次调用返回所有校验结果，方便调用方统一处理。
        /// </summary>
        public static ImportSclValidationResult ValidateImportSclComprehensive(ImportSclInput? input)
        {
            var result = new ImportSclValidationResult();

            // 1. 反序列化校验
            var (deserOk, deserErr) = ValidateImportScl(input);
            if (!deserOk)
            {
                result.Errors.Add(deserErr!);
                return result;
            }

            // 2. ProjectPath 校验
            var (pathOk, pathErr) = ValidateProjectPath(input!.ProjectPath);
            if (!pathOk)
                result.Errors.Add(pathErr!);

            // 3. SCL 文件存在性校验
            var (fileOk, fileErr) = ValidateSclFileExists(input.SclFilePath);
            if (!fileOk)
                result.Errors.Add(fileErr!);

            return result;
        }
    }

    /// <summary>
    /// import-scl 命令的综合校验结果。
    /// </summary>
    public class ImportSclValidationResult
    {
        public List<string> Errors { get; } = new List<string>();
        public bool IsValid => Errors.Count == 0;
    }
}