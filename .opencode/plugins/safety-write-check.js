const SAFETY_FILES = [
  "safety/interlock-rules.yml",
  "safety/validator.py",
  "safety/audit.py",
]

export const SafetyWriteCheck = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "write" && input.tool !== "edit") return
      const filePath = output.args.filePath?.replace(/\\/g, "/") || ""
      for (const f of SAFETY_FILES) {
        if (filePath.endsWith(f)) {
          throw new Error(`禁止直接修改安全文件 ${f}。使用 safety-audit 命令审核后手动修改。`)
        }
      }
    },
  }
}
