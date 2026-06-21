// TiaWorker JSON 辅助方法 — 镜像 Program.cs 中的 JsonOk/JsonError/DryRunResult
// ⚠️ 与 mcp-servers/tia-mcp/TiaWorker/Program.cs 保持同步
using System.Text.Json;

namespace TiaWorker
{
    public static class JsonHelpers
    {
        private static readonly JsonSerializerOptions JsonOptions = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = false
        };

        public static string JsonOk(object data)
        {
            var dict = new Dictionary<string, object?>
            {
                ["ok"] = true,
                ["result"] = data,
                ["error"] = null
            };
            return JsonSerializer.Serialize(dict, JsonOptions);
        }

        public static string JsonError(string msg)
        {
            var dict = new Dictionary<string, object?>
            {
                ["ok"] = false,
                ["result"] = null,
                ["error"] = msg
            };
            return JsonSerializer.Serialize(dict, JsonOptions);
        }

        public static string DryRunResult(string action, object previewData)
        {
            var preview = new Dictionary<string, object?>
            {
                ["dryRun"] = true,
                ["action"] = action,
                ["preview"] = previewData
            };
            return JsonOk(preview);
        }
    }
}