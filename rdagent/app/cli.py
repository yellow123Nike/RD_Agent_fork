"""
RD-Agent 命令行总入口：注册各子命令，并在最前加载当前目录下的 `.env`。

Typer 应用实例为 `app`，由 `pyproject.toml` 的 `rdagent` 脚本指向本模块。
"""

import sys

from dotenv import load_dotenv

load_dotenv(".env")
# 须在任何依赖 BaseSettings / 环境变量的 import 之前执行；显式 ".env" 表示从当前工作目录加载。

import subprocess
from importlib.resources import path as rpath
from typing import Optional

import typer
from typing_extensions import Annotated

from rdagent.app.data_science.loop import main as data_science
from rdagent.app.finetune.llm.loop import main as llm_finetune
from rdagent.app.general_model.general_model import (
    extract_models_and_implement as general_model,
)
from rdagent.app.qlib_rd_loop.factor import main as fin_factor
from rdagent.app.qlib_rd_loop.factor_from_report import main as fin_factor_report
from rdagent.app.qlib_rd_loop.model import main as fin_model
from rdagent.app.qlib_rd_loop.quant import main as fin_quant
from rdagent.app.utils.health_check import health_check
from rdagent.app.utils.info import collect_info
from rdagent.log.mle_summary import grade_summary as grade_summary

app = typer.Typer()

# 使用 Annotated + typer.Option 定义可选参数
CheckoutOption = Annotated[bool, typer.Option("--checkout/--no-checkout", "-c/-C")]
CheckEnvOption = Annotated[bool, typer.Option("--check-env/--no-check-env", "-e/-E")]
CheckDockerOption = Annotated[bool, typer.Option("--check-docker/--no-check-docker", "-d/-D")]
CheckPortsOption = Annotated[bool, typer.Option("--check-ports/--no-check-ports", "-p/-P")]


def ui(port=19899, log_dir="", debug: bool = False, data_science: bool = False):
    """启动 Streamlit 日志/轨迹 Web UI；`data_science=True` 时使用数据科学专用页面。"""
    if data_science:
        with rpath("rdagent.log.ui", "dsapp.py") as app_path:
            cmds = ["streamlit", "run", app_path, f"--server.port={port}"]
            subprocess.run(cmds)
        return
    with rpath("rdagent.log.ui", "app.py") as app_path:
        cmds = ["streamlit", "run", app_path, f"--server.port={port}"]
        if log_dir or debug:
            cmds.append("--")
        if log_dir:
            cmds.append(f"--log_dir={log_dir}")
        if debug:
            cmds.append("--debug")
        subprocess.run(cmds)


def server_ui(port=19899):
    """启动 Flask 实时日志服务（非 Streamlit）。"""
    from rdagent.log.server.app import main as log_server_main

    log_server_main(port=port)


def ds_user_interact(port=19900):
    """启动数据科学场景下的实时交互 Streamlit 页面。"""
    commands = ["streamlit", "run", "rdagent/log/ui/ds_user_interact.py", f"--server.port={port}"]
    subprocess.run(commands)


@app.command(name="fin_factor")
def fin_factor_cli(
    path: Optional[str] = None,
    step_n: Optional[int] = None,
    loop_n: Optional[int] = None,
    all_duration: Optional[str] = None,
    checkout: CheckoutOption = True,
):
    fin_factor(path=path, step_n=step_n, loop_n=loop_n, all_duration=all_duration, checkout=checkout)


@app.command(name="fin_model")
def fin_model_cli(
    path: Optional[str] = None,
    step_n: Optional[int] = None,
    loop_n: Optional[int] = None,
    all_duration: Optional[str] = None,
    checkout: CheckoutOption = True,
):
    fin_model(path=path, step_n=step_n, loop_n=loop_n, all_duration=all_duration, checkout=checkout)


@app.command(name="fin_quant")
def fin_quant_cli(
    path: Optional[str] = None,
    step_n: Optional[int] = None,
    loop_n: Optional[int] = None,
    all_duration: Optional[str] = None,
    checkout: CheckoutOption = True,
):
    fin_quant(path=path, step_n=step_n, loop_n=loop_n, all_duration=all_duration, checkout=checkout)


@app.command(name="fin_factor_report")
def fin_factor_report_cli(
    report_folder: Optional[str] = None,
    path: Optional[str] = None,
    all_duration: Optional[str] = None,
    checkout: CheckoutOption = True,
):
    fin_factor_report(report_folder=report_folder, path=path, all_duration=all_duration, checkout=checkout)


@app.command(name="general_model")
def general_model_cli(report_file_path: str):
    general_model(report_file_path)


@app.command(name="data_science")
def data_science_cli(
    path: Optional[str] = None,
    checkout: CheckoutOption = True,
    step_n: Optional[int] = None,
    loop_n: Optional[int] = None,
    timeout: Optional[str] = None,
    competition: Optional[str] = None,
):
    data_science(
        path=path,
        checkout=checkout,
        step_n=step_n,
        loop_n=loop_n,
        timeout=timeout,
        competition=competition,
    )


@app.command(name="llm_finetune")
def llm_finetune_cli(
    path: Optional[str] = None,
    checkout: CheckoutOption = True,
    benchmark: Optional[str] = None,
    benchmark_description: Optional[str] = None,
    dataset: Optional[str] = None,
    base_model: Optional[str] = None,
    upper_data_size_limit: Optional[int] = None,
    step_n: Optional[int] = None,
    loop_n: Optional[int] = None,
    timeout: Optional[str] = None,
):
    llm_finetune(
        path=path,
        checkout=checkout,
        benchmark=benchmark,
        benchmark_description=benchmark_description,
        dataset=dataset,
        base_model=base_model,
        upper_data_size_limit=upper_data_size_limit,
        step_n=step_n,
        loop_n=loop_n,
        timeout=timeout,
    )


@app.command(name="grade_summary")
def grade_summary_cli(log_folder: str):
    grade_summary(log_folder)


app.command(name="ui")(ui)
app.command(name="server_ui")(server_ui)


@app.command(name="health_check")
def health_check_cli(
    check_env: CheckEnvOption = True,
    check_docker: CheckDockerOption = True,
    check_ports: CheckPortsOption = True,
):
    """CLI：`rdagent health_check`，转调 `rdagent.app.utils.health_check.health_check`。"""
    health_check(check_env=check_env, check_docker=check_docker, check_ports=check_ports)


@app.command(name="collect_info")
def collect_info_cli():
    collect_info()


app.command(name="ds_user_interact")(ds_user_interact)


if __name__ == "__main__":
    app()
