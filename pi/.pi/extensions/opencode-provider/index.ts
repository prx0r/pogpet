import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerProvider("opencode-go", {
    name: "OpenCode Go",
    baseUrl: "https://opencode.ai/zen/go/v1",
    apiKey: process.env.OPENCODE_API_KEY || "",
    api: "openai-completions",
    models: [
      {
        id: "mimo-v2.5",
        name: "MiMo v2.5",
        reasoning: true,
        input: ["text"],
        contextWindow: 131072,
        maxOutputTokens: 16384,
      },
      {
        id: "mimo-v2.5-pro",
        name: "MiMo v2.5 Pro",
        reasoning: true,
        input: ["text"],
        contextWindow: 131072,
        maxOutputTokens: 16384,
      },
      {
        id: "deepseek-v4-flash",
        name: "DeepSeek v4 Flash",
        reasoning: false,
        input: ["text"],
        contextWindow: 131072,
        maxOutputTokens: 8192,
      },
    ],
  });
}
