// TiaWorker 参数解析逻辑 — 镜像 Program.cs 中的 Main 方法参数处理
// ⚠️ 与 mcp-servers/tia-mcp/TiaWorker/Program.cs 保持同步
using System;
using System.Collections.Generic;

namespace TiaWorker
{
    public class ArgumentParser
    {
        public bool IsDryRun { get; private set; }
        public bool IsAutoBackup { get; private set; } = true;
        public string BackupDir { get; private set; } = "";
        public string TiaMajorVersion { get; private set; } = "V18";
        public string[] RemainingArgs { get; private set; } = Array.Empty<string>();

        /// <summary>
        /// 解析命令行参数，提取 --dry-run, --no-auto-backup, --backup-dir=, --tia-major-version 等选项。
        /// 返回剩余的非选项参数。
        /// </summary>
        public string[] Parse(string[] args)
        {
            var filtered = new List<string>();
            for (int i = 0; i < args.Length; i++)
            {
                var arg = args[i];
                if (arg.Equals("--dry-run", StringComparison.OrdinalIgnoreCase))
                {
                    IsDryRun = true;
                }
                else if (arg.Equals("--no-auto-backup", StringComparison.OrdinalIgnoreCase))
                {
                    IsAutoBackup = false;
                }
                else if (arg.StartsWith("--backup-dir=", StringComparison.OrdinalIgnoreCase))
                {
                    BackupDir = arg.Substring("--backup-dir=".Length);
                }
                else if (arg.StartsWith("--tia-major-version=", StringComparison.OrdinalIgnoreCase))
                {
                    TiaMajorVersion = arg.Substring("--tia-major-version=".Length);
                }
                else if (arg.Equals("--tia-major-version", StringComparison.OrdinalIgnoreCase))
                {
                    // --tia-major-version V18 格式（取下一个 arg 作为值）
                    if (i + 1 < args.Length && !args[i + 1].StartsWith("-"))
                    {
                        TiaMajorVersion = args[i + 1];
                        i++;
                    }
                }
                else
                {
                    filtered.Add(arg);
                }
            }
            RemainingArgs = filtered.ToArray();
            return RemainingArgs;
        }
    }
}