export const EnvProtection = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "read" && output.args.filePath?.includes(".env")) {
        throw new Error("禁止读取 .env 文件，内含 API Key 等敏感信息")
      }
    },
  }
}
