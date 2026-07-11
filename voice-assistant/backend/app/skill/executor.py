from __future__ import annotations

import ast
import json
import operator as op
import re
import subprocess
import sys
from pathlib import Path

import requests

from app.skill.loader import Skill

_DATA = Path(__file__).resolve().parent.parent.parent / "data"


class _MathGuard:
    """安全数学表达式求值：仅允许 +-*/^%// 和常量，禁止函数调用/属性访问"""

    _ops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Pow: op.pow,
        ast.USub: op.neg,
        ast.Mod: op.mod,
        ast.FloorDiv: op.floordiv,
    }

    @staticmethod
    def safe_eval(expr: str):
        node = ast.parse(expr.strip(), mode="eval")
        return _MathGuard._eval(node.body)

    @staticmethod
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _MathGuard._ops:
            return _MathGuard._ops[type(node.op)](_MathGuard._eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _MathGuard._ops:
            return _MathGuard._ops[type(node.op)](
                _MathGuard._eval(node.left), _MathGuard._eval(node.right)
            )
        raise ValueError(f"unsupported expression: {type(node).__name__}")


_SYSCTL_MAP: dict[tuple[str, str], list[str]] = {
    ("shutdown", "win32"): ["shutdown", "/s", "/t", "5"],
    ("shutdown", "linux"): ["shutdown", "-h", "+1"],
    ("shutdown", "darwin"): ["shutdown", "-h", "+1"],
    ("restart", "win32"): ["shutdown", "/r", "/t", "5"],
    ("restart", "linux"): ["shutdown", "-r", "+1"],
    ("lock", "win32"): ["rundll32.exe", "user32.dll,LockWorkStation"],
    ("lock", "linux"): ["gnome-screensaver-command", "-l"],
    ("sleep", "win32"): ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"],
    ("sleep", "linux"): ["systemctl", "suspend"],
    ("hibernate", "win32"): ["shutdown", "/h"],
    ("hibernate", "linux"): ["systemctl", "hibernate"],
}


class SkillExecutor:
    def __init__(self, llm, timeout: int = 10):
        self.llm = llm
        self.timeout = timeout

    def run(self, skill: Skill, user_text: str) -> str:
        steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(skill.steps))
        sys_msg = (
            f"你正在执行技能「{skill.name}」。\n描述：{skill.description}\n步骤：\n{steps}\n"
            "先提取本技能需要的参数（如城市名），只返回参数值，不要解释。"
        )
        params_text = self.llm.chat(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_text}]
        )
        tool_results = self._call_tools(skill, params_text)
        final = self.llm.chat(
            [
                {
                    "role": "system",
                    "content": f"技能「{skill.name}」已完成工具调用，请组织成自然语言回答。工具结果：{tool_results}",
                },
                {"role": "user", "content": user_text},
            ]
        )
        return final

    def _call_tools(self, skill: Skill, params_text: str) -> str:
        tools = getattr(skill, "tools", {}) or {}
        out = []
        for name, spec in tools.items():
            typ = spec.get("type", "")
            if typ == "http":
                out.append(self._tool_http(name, spec, params_text))
            elif typ == "math":
                out.append(self._tool_math(name, params_text))
            elif typ == "localfile":
                out.append(self._tool_localfile(name, spec, params_text))
            elif typ == "sysctl":
                out.append(self._tool_sysctl(name, spec))
        return " | ".join(out) if out else ""

    def _tool_http(self, name: str, spec: dict, params_text: str) -> str:
        url = spec.get("url", "")
        for key, val in re.findall(r"\{(\w+)\}", url):
            url = url.replace("{" + key + "}", params_text.strip())
        method = spec.get("method", "GET").upper()
        resp = requests.request(method, url, timeout=self.timeout)
        return f"{name}={resp.text[:500]}"

    def _tool_math(self, name: str, expr: str) -> str:
        try:
            result = _MathGuard.safe_eval(expr)
            return f"{name}={result}"
        except Exception as e:
            return f"{name}=error:{e}"

    def _tool_localfile(self, name: str, spec: dict, params_text: str) -> str:
        path_str = spec.get("path", "todo.json")
        p = (_DATA / path_str).resolve()
        if not str(p).startswith(str(_DATA.resolve())):
            return f"{name}=error:path traversal denied"
        p.parent.mkdir(parents=True, exist_ok=True)
        arr = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        arr.append(params_text.strip())
        p.write_text(json.dumps(arr, ensure_ascii=False), encoding="utf-8")
        return f"{name}=saved"

    def _tool_sysctl(self, name: str, spec: dict) -> str:
        cmd_key = spec.get("command", "")
        plat = sys.platform
        cmd = _SYSCTL_MAP.get((cmd_key, plat))
        if not cmd:
            return f"{name}=error:command not allowed or unsupported platform"
        try:
            subprocess.run(cmd, shell=False, timeout=self.timeout)
            return f"{name}=ok"
        except Exception as e:
            return f"{name}=error:{e}"