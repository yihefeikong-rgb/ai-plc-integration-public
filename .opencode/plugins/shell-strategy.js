const INTERACTIVE_COMMANDS = ["pip", "npm install", "npx", "yarn", "ssh", "telnet", "python -m pdb"]

export const ShellStrategy = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "bash") return
      const cmd = output.args.command?.toLowerCase() || ""
      for (const bad of INTERACTIVE_COMMANDS) {
        if (cmd.includes(bad) && !cmd.includes("yes ") && !cmd.includes("/y") && !cmd.includes("-y") && !cmd.includes("--yes")) {
          output.args.command = `set "PIP_NO_INPUT=1" && set "TERM=dumb" && ${output.args.command}`
          break
        }
      }
    },
  }
}
