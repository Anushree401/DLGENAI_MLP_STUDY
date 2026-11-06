import crypto from "node:crypto";
import { Sandbox } from "@vercel/sandbox";

export const maxDuration = 300;

const MAX_CODE_LENGTH = 100_000;
const MAX_HISTORY_CELLS = 100;
const MAX_HISTORY_LENGTH = 500_000;

function send(response, body, status = 200) {
  response.status(status).json(body);
}

function sandboxName(session, token) {
  const digest = crypto.createHash("sha256").update(`${token}:${session}`).digest("hex");
  return `study-notes-${digest.slice(0, 40)}`;
}

const RUNNER = String.raw`
import base64
import contextlib
import io
import json
import traceback

payload = json.load(open("/vercel/sandbox/study-payload.json", encoding="utf-8"))
namespace = {"__name__": "__main__"}
history_stdout = io.StringIO()
history_stderr = io.StringIO()

try:
    with contextlib.redirect_stdout(history_stdout), contextlib.redirect_stderr(history_stderr):
        for position, previous_code in enumerate(payload["history"]):
            exec(compile(previous_code, f"<previous-cell-{{position + 1}}>", "exec"), namespace, namespace)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.close("all")
    except Exception:
        plt = None

    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exec(compile(payload["code"], "<current-cell>", "exec"), namespace, namespace)

    images = []
    if plt is not None:
        for number in plt.get_fignums():
            figure = plt.figure(number)
            buffer = io.BytesIO()
            figure.savefig(buffer, format="png", bbox_inches="tight", dpi=120)
            images.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
        plt.close("all")
    result = {"ok": True, "stdout": stdout.getvalue(), "stderr": stderr.getvalue(), "images": images}
except BaseException:
    result = {"ok": False, "stdout": "", "stderr": traceback.format_exc(), "images": []}

print("__STUDY_RESULT__" + json.dumps(result))
`;

async function createStudySandbox(name) {
  return Sandbox.getOrCreate({
    name,
    runtime: "python3.13",
    timeout: 5 * 60 * 1000,
    onCreate: async (sandbox) => {
      const install = await sandbox.runCommand({
        cmd: "python3",
        args: [
          "-m", "pip", "install", "--disable-pip-version-check", "--quiet",
          "numpy", "pandas", "matplotlib", "scikit-learn", "torch",
        ],
      });
      if (install.exitCode !== 0) {
        throw new Error(`Python environment setup failed: ${await install.stderr()}`);
      }
    },
  });
}

export default async function handler(request, response) {
  if (request.method !== "POST") {
    return send(response, { error: "Use POST." }, 405);
  }

  const expectedToken = process.env.STUDY_RUNNER_TOKEN;
  const { code, history = [], session, token } = request.body ?? {};
  if (!expectedToken) {
    return send(response, { error: "The host has not configured STUDY_RUNNER_TOKEN." }, 503);
  }
  const suppliedToken = Buffer.from(String(token ?? ""));
  const configuredToken = Buffer.from(expectedToken);
  if (suppliedToken.length !== configuredToken.length || !crypto.timingSafeEqual(suppliedToken, configuredToken)) {
    return send(response, { error: "Runner key rejected." }, 401);
  }
  if (typeof session !== "string" || !/^[A-Za-z0-9_.-]{1,120}$/.test(session)) {
    return send(response, { error: "Invalid study session." }, 400);
  }
  if (typeof code !== "string" || code.length > MAX_CODE_LENGTH) {
    return send(response, { error: "Code cell is missing or too large." }, 413);
  }
  if (!Array.isArray(history) || history.length > MAX_HISTORY_CELLS || history.some((item) => typeof item !== "string") || history.join("").length > MAX_HISTORY_LENGTH) {
    return send(response, { error: "Invalid execution history." }, 400);
  }

  try {
    const sandbox = await createStudySandbox(sandboxName(session, expectedToken));
    await sandbox.writeFiles([
      { path: "/vercel/sandbox/study-runner.py", content: Buffer.from(RUNNER) },
      { path: "/vercel/sandbox/study-payload.json", content: Buffer.from(JSON.stringify({ history, code })) },
    ]);
    const run = await sandbox.runCommand({ cmd: "python3", args: ["/vercel/sandbox/study-runner.py"] });
    const output = await run.stdout();
    const match = output.match(/__STUDY_RESULT__(\{[\s\S]*\})\s*$/);
    if (!match) {
      const stderr = await run.stderr();
      return send(response, { ok: false, stdout: output, stderr: stderr || "The sandbox returned no structured result.", images: [] }, 500);
    }
    return send(response, JSON.parse(match[1]));
  } catch (error) {
    return send(response, { ok: false, stdout: "", stderr: error instanceof Error ? error.message : String(error), images: [] }, 500);
  }
}
