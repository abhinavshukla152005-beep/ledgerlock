from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any

from .config import settings


@dataclass
class SandboxResult:
    ok: bool
    backend: str
    containment: str
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    duration_ms: int
    payload: Any | None
    error: str | None = None


def _extract(stdout: str, marker: str) -> Any | None:
    for line in reversed(stdout.strip().splitlines()):
        if line.startswith(f"{marker}:"):
            try:
                return json.loads(line[len(marker) + 1 :])
            except json.JSONDecodeError:
                return None
    return None


def run(script: str, inputs: dict[str, Any], marker: str = "RESULT") -> SandboxResult:
    if settings.sandbox_backend == "docker":
        return _run_docker(script, inputs, marker)
    return _run_local(script, inputs, marker)


def _write_workspace(script: str, inputs: dict[str, Any]) -> str:
    root = settings.sandbox_work_root or None
    if root:
        os.makedirs(root, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="ledgerlock-", dir=root)
    script_path = os.path.join(workdir, "run.py")
    input_path = os.path.join(workdir, "input.json")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(script)
    with open(input_path, "w", encoding="utf-8") as handle:
        json.dump(inputs, handle)
    # The sandbox runs as uid 65534; the workspace is bind-mounted read-only.
    os.chmod(workdir, 0o755)
    os.chmod(script_path, 0o644)
    os.chmod(input_path, 0o644)
    return workdir


def _run_local(script: str, inputs: dict[str, Any], marker: str) -> SandboxResult:
    workdir = _write_workspace(script, inputs)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-B", os.path.join(workdir, "run.py")],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=settings.sandbox_timeout,
            env={
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "TMPDIR": workdir,
                "LEDGERLOCK_INPUT": os.path.join(workdir, "input.json"),
                "PATH": os.environ.get("PATH", ""),
            },
        )
        duration = int((time.monotonic() - started) * 1000)
        return SandboxResult(
            ok=proc.returncode == 0,
            backend="local",
            containment="none (development fallback)",
            exit_code=proc.returncode,
            timed_out=False,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_ms=duration,
            payload=_extract(proc.stdout, marker),
        )
    except subprocess.TimeoutExpired as exc:
        duration = int((time.monotonic() - started) * 1000)
        return SandboxResult(
            ok=False,
            backend="local",
            containment="none (development fallback)",
            exit_code=None,
            timed_out=True,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
            duration_ms=duration,
            payload=None,
            error="timeout",
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _create_container(client: Any, workdir: str) -> Any:
    import docker

    kwargs: dict[str, Any] = dict(
        image=settings.sandbox_image,
        command=["python", "-B", "/workspace/run.py"],
        network_disabled=True,
        mem_limit="256m",
        memswap_limit="256m",
        pids_limit=64,
        cpu_period=100000,
        cpu_quota=50000,
        read_only=True,
        tmpfs={"/tmp": "size=64m,noexec,nosuid"},
        working_dir="/workspace",
        user="65534:65534",
        volumes={workdir: {"bind": "/workspace", "mode": "ro"}},
        environment={
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "TMPDIR": "/tmp",
            "HOME": "/tmp",
        },
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
    )
    try:
        return client.containers.create(**kwargs)
    except docker.errors.ImageNotFound:
        client.images.pull(settings.sandbox_image)
        return client.containers.create(**kwargs)


def _run_docker(script: str, inputs: dict[str, Any], marker: str) -> SandboxResult:
    import docker  # imported lazily so local dev does not need the SDK

    workdir = _write_workspace(script, inputs)
    started = time.monotonic()
    container = None
    try:
        client = docker.from_env()
        container = _create_container(client, workdir)
        container.start()
        timed_out = False
        try:
            container.wait(timeout=settings.sandbox_timeout)
        except Exception:
            timed_out = True
            container.kill()
        logs = container.logs(stdout=True, stderr=False).decode("utf-8", "replace")
        err = container.logs(stdout=False, stderr=True).decode("utf-8", "replace")
        state = container.attrs.get("State", {})
        exit_code = state.get("ExitCode")
        duration = int((time.monotonic() - started) * 1000)
        return SandboxResult(
            ok=(exit_code == 0 and not timed_out),
            backend="docker",
            containment="docker: no network, read-only root, cap-drop ALL, pids/mem/cpu caps",
            exit_code=exit_code,
            timed_out=timed_out,
            stdout=logs,
            stderr=err,
            duration_ms=duration,
            payload=_extract(logs, marker),
        )
    except Exception as exc:  # docker unavailable or daemon error
        duration = int((time.monotonic() - started) * 1000)
        return SandboxResult(
            ok=False,
            backend="docker",
            containment="unavailable",
            exit_code=None,
            timed_out=False,
            stdout="",
            stderr="",
            duration_ms=duration,
            payload=None,
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass
        shutil.rmtree(workdir, ignore_errors=True)
