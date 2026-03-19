#!/usr/bin/env python

# High-level build script for all of Pandora.
#
# This script is responsible for:
#
# - Cloning the required repositories for Pandora:
#
#   - PandoraSDK
#   - PandoraPFA
#   - LArContent
#   - LArReco or LArRecoND
#   - LArMachineLearningData
#   - Eigen
#   - (optionally) PandoraMonitoring
#   - (optionally) LibTorch
#   - (optionally) TorchSparse/TorchScatter
#
# - Building the code in the correct order, with the correct CMake flags, and
# handling any platform-specific issues that arise.

import argparse
import glob
import os
import platform
import shlex
import subprocess
import sys
from datetime import datetime
from enum import Enum

# Repo URLs
BASE_REPO = "https://github.com/PandoraPFA"
PFA = f"{BASE_REPO}/PandoraPFA.git"
SDK = f"{BASE_REPO}/PandoraSDK.git"
MACHINELEARNING = f"{BASE_REPO}/LArMachineLearningData.git"
MONITORING = f"{BASE_REPO}/PandoraMonitoring.git"
LARCONTENT = f"{BASE_REPO}/LArContent.git"
LARRECO = f"{BASE_REPO}/LArReco.git"
LARRECOND = f"{BASE_REPO}/LArRecoND.git"
EIGEN = "https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.tar.gz"

# Versions...
LIBTORCH_VERSION = "v2.2.0"
CXX_STANDARD = "17"

# LibTorch / DL Specific
TORCH = "https://github.com/pytorch/pytorch.git"
LINUX_URL = "https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-2.5.0%2Bcpu.zip"
MAC_URL = "https://download.pytorch.org/libtorch/cpu/libtorch-macos-1.9.0.zip"
MAC_ARM_URL = "https://download.pytorch.org/libtorch/cpu/libtorch-macos-arm64-2.3.1.zip"
PYTORCH_SPARSE = "https://github.com/rusty1s/pytorch_sparse.git"
PYTORCH_SCATTER = "https://github.com/rusty1s/pytorch_scatter.git"
PYTORCH_CLUSTER = "https://github.com/rusty1s/pytorch_cluster.git"

# Determine the platform we are building on
PRE_BUILT_LIBTORCH = LINUX_URL

# If we are on Mac, we need to use the Mac version of LibTorch, and if we are on
# an ARM-based Mac, we need to use the ARM version of LibTorch.
if platform.system() == "Darwin" and platform.processor() == "arm":
    PRE_BUILT_LIBTORCH = MAC_ARM_URL
elif platform.system() == "Darwin":
    PRE_BUILT_LIBTORCH = MAC_URL

# The list of required packages for the build
REQUIRED_PACKAGES = [
    ("cmake", ["cmake", "--version"]),
    ("ninja", ["ninja", "--version"]),
    ("git", ["git", "--version"]),
    ("curl", ["curl", "--version"]),
    ("python", ["python", "--version"]),
    ("tar", ["tar", "--version"]),
]
BUILD_GEN = "-GNinja"


# ANSI colour codes for terminal output
class Colours(Enum):
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    RESET = "\033[0m"


# Debugging levels
class Debug(Enum):
    Info = 0
    Warn = 1
    Error = 2


# Logging helper functions:
#  - Info: Print information to stdout
#  - Warn: Print warning to stderr, in yellow
#  - Error: Print error to stderr, in red
def _log(message, colour=Colours.GREEN):
    date_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{colour.value}{date_time_str} : {message}{Colours.RESET.value}")


def info(message) -> None:
    _log(f"INFO   : {message}")


def info_banner(message) -> None:
    _log(f"{'=' * 40}")
    _log(f"INFO   : {message}")
    _log(f"{'=' * 40}")


def warn(message) -> None:
    _log(f"WARN   : {message}", Colours.YELLOW)


def error(message) -> None:
    _log(f"ERR   : {message}", Colours.RED)


def run_command(
    args,
    command,
    message,
    error_message,
    warn_level=Debug.Info,
    silent=False,
    cwd=None,
) -> None:
    command_string = command if isinstance(command, str) else " ".join(command)

    if args.verbose:
        info(f"Full command: {command_string}")

    if message:
        info(message)

    if getattr(args, "dry_run", False):
        info(f"DRY-RUN: {command_string}")
        return

    capture = silent or args.quiet

    if args.verbose:
        capture = False

    use_shell = isinstance(command, str)

    try:
        subprocess.run(
            command,
            shell=use_shell,
            check=True,
            capture_output=capture,
            cwd=cwd,
        )
    except subprocess.CalledProcessError as e:
        if warn_level == Debug.Warn:
            warn(f"{error_message}: {e}")
        else:
            error(f"{error_message}: {e}")
            sys.exit(1)


# Parse the command line arguments for the script.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Pandora")

    # Required arguments
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output directory for the build.",
        type=os.path.abspath,
    )

    # Build step arguments
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force a clean build of Pandora.",
        default=False,
    )
    parser.add_argument(
        "-c",
        "--clone_only",
        action="store_true",
        help="Only clone the Pandora repositories, then exit.",
        default=False,
    )

    # Build configuration arguments:
    # - These arguments are used to configure the build of Pandora, such as DL libraries, etc.
    parser.add_argument(
        "-M",
        "--build_monitoring",
        action="store_true",
        help="Enable monitoring support in Pandora (on by default).",
        default=True,
    )
    parser.add_argument(
        "-N",
        "--build_near_detector",
        action="store_true",
        help="Build LArReoND, rather than LArReco, enabling ND support.",
        default=False,
    )

    # What ML data to download? Defaults to "dune".
    parser.add_argument(
        "-m",
        "--download_data",
        help="Download the ML data for the specified detector.",
        default="dune",
    )

    # Specific DL library arguments:
    # - Should we build LibTorch from scratch, or use a pre-built version?
    # - Should we try and bring in TorchSparse support?
    parser.add_argument(
        "-d",
        "--download_libtorch",
        action="store_true",
        help="Download LibTorch from PyTorch.",
        default=False,
    )
    parser.add_argument(
        "-D",
        "--build_libtorch",
        action="store_true",
        help="Build LibTorch from source.",
        default=False,
    )
    parser.add_argument(
        "-I",
        "--prebuilt_libtorch",
        help="Path to a pre-built LibTorch folder",
        default=False,
    )
    parser.add_argument(
        "-L",
        "--larsoft_libtorch",
        action="store_true",
        help="Use the version of LibTorch provided by LArSoft (if available).",
        default=False,
    )

    parser.add_argument(
        "-S",
        "--sparse_support",
        action="store_true",
        help="Build TorchSparse + TorchScatter.",
        default=False,
    )
    parser.add_argument(
        "-s",
        "--sparse_path",
        help="Path to TorchSparse/TorchScatter build to use",
        default=False,
    )

    # Add an optional ROOT path, if its not being picked up from the environment
    parser.add_argument(
        "-r",
        "--root_path",
        help="Path to a ROOT installation, if not picked up from env.",
        default="",
    )

    # Debugging arguments
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Disable more output.",
        default=False,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable even more output.",
        default=False,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
        default=False,
    )

    # Show the help message if no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    if args.build_near_detector:
        args.download_data = "dunend"

    return args


def patch_file(file_path, search_str, replace_str) -> None:
    with open(file_path, "r") as file:
        lines = file.readlines()

    new_lines = lines.copy()

    for i, line in enumerate(lines):
        if search_str == line.strip():
            info(f"Found {search_str} in {file_path}, patching...")
            new_lines[i] = replace_str + "\n"

    if new_lines == lines:
        warn(f"Did not find {search_str} in {file_path}, skipping patching...")
        warn("Please check the file for any issues...")
    else:
        with open(file_path, "w") as file:
            file.writelines(new_lines)
            info(f"Patched {file_path}...")


def clone_command(repo: str, git_flags: str = "") -> list[str]:
    command = ["git", "clone", repo]
    if git_flags:
        command.extend(shlex.split(git_flags))
    return command


def clone_repo(args, repo, command, cwd=None) -> None:
    if os.path.exists(f"{args.output}/{repo}"):
        info(f"{repo} already exists, skipping...")
        return

    run_command(
        args,
        command,
        f"Cloning {repo}...",
        f"Failed to clone {repo}",
        Debug.Error,
        cwd=cwd,
    )


def get_code(args) -> None:
    clone_repo(args, "PandoraSDK", clone_command(SDK), cwd=args.output)
    clone_repo(args, "PandoraPFA", clone_command(PFA), cwd=args.output)

    if args.build_monitoring:
        clone_repo(
            args, "PandoraMonitoring", clone_command(MONITORING), cwd=args.output
        )

    clone_repo(args, "LArContent", clone_command(LARCONTENT), cwd=args.output)

    lar_reco_dir = "LArReco" if not args.build_near_detector else "LArRecoND"
    lar_reco_repo = LARRECO if not args.build_near_detector else LARRECOND
    clone_repo(args, lar_reco_dir, clone_command(lar_reco_repo), cwd=args.output)

    clone_repo(
        args, "LArMachineLearningData", clone_command(MACHINELEARNING), cwd=args.output
    )

    clone_repo(
        args,
        "Eigen3",
        f"curl -L {EIGEN} --output {args.output}/eigen.tar.gz",
    )

    # Work out if we need to get some form of LibTorch...
    # We can either build it, download it or use a pre-built version.
    if args.build_libtorch:
        clone_repo(
            args,
            "pytorch",
            clone_command(TORCH, f"--recurse-submodules -b {LIBTORCH_VERSION}"),
            cwd=args.output,
        )
    elif args.download_libtorch:
        clone_repo(
            args,
            "libtorch",
            f"curl -L {PRE_BUILT_LIBTORCH} --output {args.output}/libtorch.zip",
        )
    elif args.prebuilt_libtorch:
        info(f"Using pre-built LibTorch from: {args.prebuilt_libtorch}")
    elif args.larsoft_libtorch:
        info("Using LArSoft-provided LibTorch (if available).")

    # Similarly, if we are building TorchSparse, we need to clone it...
    if args.sparse_support:
        clone_repo(
            args,
            "pytorch_sparse",
            clone_command(PYTORCH_SPARSE, "--recurse-submodules"),
            cwd=args.output,
        )
        clone_repo(
            args,
            "pytorch_scatter",
            clone_command(PYTORCH_SCATTER),
            cwd=args.output,
        )
        clone_repo(
            args,
            "pytorch_cluster",
            clone_command(PYTORCH_CLUSTER),
            cwd=args.output,
        )
    elif args.sparse_path:
        info(f"Using pre-built TorchSparse/TorchScatter from: {args.sparse_path}")


def build_repo(
    args, target_repo: str, build_command: str, alt_install_command: str = ""
) -> None:
    build_dir = f"{args.output}/{target_repo}/build"

    if os.path.exists(f"{args.output}/{target_repo}/build") and args.force:
        run_command(
            args,
            ["rm", "-rf", build_dir],
            f"Removing existing build directory for {target_repo}...",
            f"Failed to remove existing build directory for {target_repo}",
            Debug.Error,
        )

    if os.path.exists(build_dir):
        info(f"Build directory for {target_repo} already exists, skipping...")
        return

    info_banner(f"Building {target_repo}...")
    if args.dry_run:
        info(f"DRY-RUN: create directory {build_dir}")
    else:
        os.makedirs(build_dir, exist_ok=True)
        info(f"Creating build directory for {target_repo}...")

    run_command(
        args,
        build_command,
        f"Running build command for {target_repo}...",
        f"Failed to build {target_repo}",
        Debug.Error,
        cwd=build_dir,
    )

    run_command(
        args,
        ["ninja", "install"] if not alt_install_command else alt_install_command,
        f"Running install command for {target_repo}...",
        f"Failed to install {target_repo}",
        Debug.Error,
        cwd=build_dir,
    )


def build_libtorch(args) -> None:
    info_banner("Building LibTorch...")

    # First, check the git repo is on the correct branch
    git_tags = subprocess.run(
        f"git -C {args.output}/pytorch describe --tags",
        shell=True,
        check=True,
        capture_output=True,
    )

    if git_tags.stdout.strip().decode("utf-8") == LIBTORCH_VERSION:
        info("PyTorch is on the correct version...")
    else:
        run_command(
            args,
            f"git -C {args.output}/pytorch checkout {LIBTORCH_VERSION}",
            "Checking out the correct version of PyTorch...",
            "Failed to checkout the correct version of PyTorch",
            Debug.Error,
        )

        # And update the submodules
        run_command(
            args,
            f"git -C {args.output}/pytorch submodule update --init --recursive",
            "Updating the submodules...",
            "Failed to update the submodules",
            Debug.Error,
        )

    venv_folder = f"{args.output}/pytorch_venv"
    python_bin = f"{venv_folder}/bin/python"

    if os.path.exists(venv_folder):
        info("Virtual environment already exists...")
    else:
        run_command(
            args,
            f"python3 -m venv {venv_folder}",
            "Creating a virtual environment for PyTorch...",
            "Failed to create a virtual environment for PyTorch",
            Debug.Error,
        )

        # Check the requirements.txt file...
        # numpy 2.0 and higher deprecated a bunch of things,
        # and older versions of PyTorch did not pin numpy to a version.
        #
        # So, lets check the version of numpy in the requirements.txt file
        # and replace it with a version that works with the PyTorch version we are using.
        requirements_file = f"{args.output}/pytorch/requirements.txt"
        patch_file(
            f"{args.output}/pytorch/requirements.txt",
            "numpy",
            "numpy==1.26.4",
        )

        # Now we can install the requirements
        run_command(
            args,
            f"{python_bin} -m pip install -r {requirements_file}",
            "Setting up Python Venv...",
            "Failed to setup PyTorch Python Venv",
            Debug.Error,
        )

    # Finally, we can now build PyTorch
    if os.path.exists(f"{args.output}/libtorch-build"):
        info("LibTorch already exists, skipping...")
        return

    libtorch_build = f"{args.output}/libtorch-build"
    os.makedirs(libtorch_build, exist_ok=True)
    libtorch_install = f"{args.output}/libtorch-install"
    os.makedirs(libtorch_install, exist_ok=True)

    info("Setting up LibTorch CMake config...")
    libtorch_cmake_flags = "-DBUILD_SHARED_LIBS=ON"
    libtorch_cmake_flags += " -DCMAKE_BUILD_TYPE=Release"
    libtorch_cmake_flags += f" -DCMAKE_INSTALL_PREFIX={libtorch_install}"
    libtorch_cmake_flags += f" -DPYTHON_EXECUTABLE={python_bin}"
    libtorch_cmake_flags += f" -DCMAKE_CXX_STANDARD={CXX_STANDARD}"
    libtorch_cmake_flags += f" {BUILD_GEN}"

    run_command(
        args,
        f"cd {libtorch_build} && cmake {libtorch_cmake_flags} ../pytorch",
        "Configuring LibTorch...",
        "Failed to configure LibTorch",
        Debug.Error,
    )

    run_command(
        args,
        f"cmake --build {libtorch_build} --target install",
        "Building LibTorch...",
        "Failed to build LibTorch",
        Debug.Error,
    )

    info_banner("LibTorch build complete...")

    return


def prepare_archives(args) -> None:
    """Extract downloaded archive artifacts if present."""
    if os.path.exists(f"{args.output}/eigen.tar.gz"):
        run_command(
            args,
            ["tar", "-xzf", f"{args.output}/eigen.tar.gz", "-C", args.output],
            "Extracting Eigen...",
            "Failed to extract Eigen",
            Debug.Error,
        )
        if args.dry_run:
            run_command(
                args,
                f"mv {args.output}/eigen-* {args.output}/Eigen3",
                "Moving Eigen...",
                "Failed to rename Eigen",
                Debug.Error,
            )
            run_command(
                args,
                ["rm", "-f", f"{args.output}/eigen.tar.gz"],
                "Removing Eigen archive...",
                "Failed to remove Eigen archive",
                Debug.Error,
            )
            return

        candidates = sorted(glob.glob(f"{args.output}/eigen-*"))
        if not candidates:
            error("Failed to locate extracted Eigen directory")
            sys.exit(1)
        run_command(
            args,
            ["mv", candidates[0], f"{args.output}/Eigen3"],
            "Moving Eigen...",
            "Failed to rename Eigen",
            Debug.Error,
        )
        run_command(
            args,
            ["rm", "-f", f"{args.output}/eigen.tar.gz"],
            "Removing Eigen archive...",
            "Failed to remove Eigen archive",
            Debug.Error,
        )

    if os.path.exists(f"{args.output}/libtorch.zip"):
        run_command(
            args,
            [
                "python3",
                "-m",
                "zipfile",
                "-e",
                f"{args.output}/libtorch.zip",
                args.output,
            ],
            "Extracting LibTorch...",
            "Failed to extract LibTorch",
            Debug.Error,
        )
        run_command(
            args,
            ["rm", "-f", f"{args.output}/libtorch.zip"],
            "Removing LibTorch archive...",
            "Failed to remove LibTorch archive",
            Debug.Error,
        )


def build_common_flags(args) -> dict[str, str]:
    """Assemble common CMake flags shared across repository builds."""
    rootsys = args.root_path if args.root_path else os.environ.get("ROOTSYS", "")
    root_cmake = f"{rootsys}/etc/cmake" if rootsys else ""

    if not os.path.exists(root_cmake) and rootsys:
        root_cmake = f"{rootsys}/cmake"

    cmake_module_path = f"-DCMAKE_MODULE_PATH={args.output}/PandoraPFA/cmakemodules"
    root_cmake_module_path = (
        f'-DCMAKE_MODULE_PATH="{args.output}/PandoraPFA/cmakemodules;{root_cmake}" '
        f"-DCMAKE_CXX_STANDARD={CXX_STANDARD}"
    )
    pandora_sdk = (
        f"-DPandoraSDK_DIR={args.output}/PandoraSDK/build/install/lib/cmake/PandoraSDK"
    )
    pandora_monitoring = (
        f"-DPANDORA_MONITORING={args.build_monitoring} "
        f"-DPandoraMonitoring_DIR={args.output}/PandoraMonitoring/build/install/lib/cmake/PandoraMonitoring"
    )
    eigen_flag = f"-DEigen3_DIR={args.output}/Eigen3/share/eigen3/cmake/"
    larcontent_flag = (
        f"-DLArContent_DIR={args.output}/LArContent/build/install/lib/cmake/LArContent"
    )

    return {
        "cmake_module_path": cmake_module_path,
        "root_cmake_module_path": root_cmake_module_path,
        "pandora_sdk": pandora_sdk,
        "pandora_monitoring": pandora_monitoring,
        "eigen_flag": eigen_flag,
        "larcontent_flag": larcontent_flag,
    }


def apply_dl_flags(
    args, lar_content_build_flags: str, lar_reco_build_flags: str
) -> tuple[str, str, dict[str, str]]:
    """Append deep-learning related CMake flags when requested."""
    sparse_commands: dict[str, str] = {}
    use_dl = (
        args.download_libtorch
        or args.build_libtorch
        or args.prebuilt_libtorch
        or args.larsoft_libtorch
    )

    if not use_dl:
        return lar_content_build_flags, lar_reco_build_flags, sparse_commands

    torch_dir = ""
    if args.download_libtorch:
        torch_dir = f"{args.output}/libtorch"
    elif args.prebuilt_libtorch:
        torch_dir = f"{args.prebuilt_libtorch}"
    elif args.build_libtorch:
        torch_dir = f"{args.output}/libtorch-install"

    sparse_dir = ""
    scatter_dir = ""
    cluster_dir = ""

    if args.sparse_support:
        sparse_dir = f"{args.output}/pytorch_sparse/install/share/cmake/TorchSparse"
        scatter_dir = f"{args.output}/pytorch_scatter/install/share/cmake/TorchScatter"
        cluster_dir = f"{args.output}/pytorch_cluster/install/share/cmake/TorchCluster"
    elif args.sparse_path:
        sparse_dir = f"{args.sparse_path}/pytorch_sparse/install"
        scatter_dir = f"{args.sparse_path}/pytorch_scatter/install"
        cluster_dir = f"{args.sparse_path}/pytorch_cluster/install"

    cmake_prefix_torch = f'-DCMAKE_PREFIX_PATH="{torch_dir}"'
    all_torch_cmake = f'-DCMAKE_PREFIX_PATH="{torch_dir}"'

    if args.sparse_support or args.sparse_path:
        all_torch_cmake = f'-DCMAKE_PREFIX_PATH="{torch_dir};{sparse_dir};{scatter_dir};{cluster_dir}"'

    libtorch_flag = "-DPANDORA_LIBTORCH=ON"
    dl_content = f"-DLArDLContent_DIR={args.output}/LArContent/build/install/lib/cmake/LArDLContent"

    sparse_commands = {
        "pytorch_sparse": f"cmake {cmake_prefix_torch} -DCMAKE_INSTALL_PREFIX={args.output}/pytorch_sparse/install {BUILD_GEN} ..",
        "pytorch_scatter": f"cmake {cmake_prefix_torch} -DCMAKE_INSTALL_PREFIX={args.output}/pytorch_scatter/install {BUILD_GEN} ..",
        "pytorch_cluster": f"cmake {cmake_prefix_torch} -DCMAKE_INSTALL_PREFIX={args.output}/pytorch_cluster/install {BUILD_GEN} ..",
    }

    lar_content_build_flags += f" {libtorch_flag} {all_torch_cmake}"
    lar_reco_build_flags += f" {libtorch_flag} {all_torch_cmake} {dl_content}"

    return lar_content_build_flags, lar_reco_build_flags, sparse_commands


def download_ml_data_if_needed(args) -> None:
    """Download machine-learning data only when absent."""
    if os.path.exists(f"{args.output}/LArMachineLearningData/PandoraMVAData"):
        warn("PandoraMVAData already exists, skipping...")
        return

    ml_download_commands = f"export MY_TEST_AREA={args.output};"
    download_target = "dune lbl" if args.download_data == "dune" else args.download_data
    ml_download_commands = f"{ml_download_commands} bash {args.output}/LArMachineLearningData/download.sh {download_target}"

    run_command(
        args,
        ml_download_commands,
        "Downloading ML data...",
        "Failed to download ML data",
        Debug.Error,
    )


def build_sparse_dependencies(args, sparse_commands: dict[str, str]) -> None:
    """Build sparse dependencies when requested by flags."""
    if not args.sparse_support:
        return

    patch_file(
        f"{args.output}/pytorch_sparse/CMakeLists.txt",
        "set(CMAKE_CXX_STANDARD 14)",
        f"set(CMAKE_CXX_STANDARD {CXX_STANDARD})",
    )
    patch_file(
        f"{args.output}/pytorch_cluster/CMakeLists.txt",
        "set(CMAKE_CXX_STANDARD 14)",
        f"set(CMAKE_CXX_STANDARD {CXX_STANDARD})",
    )

    build_repo(args, "pytorch_sparse", sparse_commands["pytorch_sparse"])
    build_repo(args, "pytorch_scatter", sparse_commands["pytorch_scatter"])
    build_repo(args, "pytorch_cluster", sparse_commands["pytorch_cluster"])


def build_code(args) -> None:
    # Double check the environment is setup correctly
    # We dont want to go via cetbuildtools, so unset it
    if "CETBUILDTOOLS_VERSION" in os.environ:
        warn("Unsetting CETBUILDTOOLS_VERSION, to avoid cetbuildtools")
        os.environ.pop("CETBUILDTOOLS_VERSION")

    prepare_archives(args)

    # If we are only cloning, then exit here
    if args.clone_only:
        sys.exit(0)

    common_flags = build_common_flags(args)
    cmake_module_path = common_flags["cmake_module_path"]
    root_cmake_module_path = common_flags["root_cmake_module_path"]
    pandora_sdk = common_flags["pandora_sdk"]
    pandora_monitoring = common_flags["pandora_monitoring"]
    eigen_flag = common_flags["eigen_flag"]
    larcontent_flag = common_flags["larcontent_flag"]

    lar_content_build_flags = (
        f"{root_cmake_module_path} {pandora_sdk} {pandora_monitoring} {eigen_flag}"
    )
    lar_reco_build_flags = (
        f"{root_cmake_module_path} {pandora_sdk} {pandora_monitoring} {larcontent_flag}"
    )

    lar_content_build_flags, lar_reco_build_flags, sparse_commands = apply_dl_flags(
        args, lar_content_build_flags, lar_reco_build_flags
    )

    # Finally, get back to the building and start the build process

    # Eigen is quick, and we need it for everything, so build it first
    build_repo(
        args,
        "Eigen3",
        f"cmake -DCMAKE_INSTALL_PREFIX={args.output}/Eigen3/ {BUILD_GEN} ..",
    )

    # Then get the other easy bits sorted, starting with pulling down the ML data
    download_ml_data_if_needed(args)

    # Finally, the SDK, which is needed for everything else
    build_repo(args, "PandoraSDK", f"cmake {cmake_module_path} {BUILD_GEN} ..")

    # Now we can start on the optional bits, starting with the monitoring
    if args.build_monitoring:
        build_repo(
            args,
            "PandoraMonitoring",
            f"cmake {root_cmake_module_path} {pandora_sdk} {BUILD_GEN} ..",
        )

    # Before moving to the optional DL libraries...
    if args.build_libtorch:
        build_libtorch(args)

    build_sparse_dependencies(args, sparse_commands)

    # And finally, the main event, the LArContent and LArReco
    lar_reco_dir = "LArReco" if not args.build_near_detector else "LArRecoND"
    build_repo(args, "LArContent", f"cmake {lar_content_build_flags} {BUILD_GEN} ..")
    build_repo(args, lar_reco_dir, f"cmake {lar_reco_build_flags} {BUILD_GEN} ..")


def main() -> None:
    args = parse_args()
    cwd = os.getcwd()

    # Check we have the required packages installed
    for package, command in REQUIRED_PACKAGES:
        run_command(
            args,
            command,
            "",
            f"Could not find {package}",
            Debug.Error,
            silent=True,
        )

    # Check if the output directory exists, if not create it and any parent directories
    if not os.path.exists(args.output):
        if args.dry_run:
            info(f"DRY-RUN: create directory {args.output}")
        else:
            os.makedirs(args.output)

    # Change to the output directory
    os.chdir(args.output)

    # Get the code from the repositories...
    info_banner("Cloning required repositories...")
    get_code(args)
    info_banner("Cloning complete...")

    # Then build the code
    info_banner("Starting to build...")
    build_code(args)
    info_banner("Build complete...")

    # Return to the original directory
    os.chdir(cwd)

    # Everything is done!
    # Alert the user on the next steps...
    warn(f"Only the ML data for {args.download_data.upper()} has been downloaded...")
    warn("Download other data files as required.")
    warn("The script for this lives is:")
    warn(f"{args.output}/LArMachineLearningData/download.sh")

    info("All done! Pandora is now built and ready to use.")
    info("Setup any environment variables to locate configs as needed.")
    info("Re-build things using ninja in the relevant build folder.")


# Run the main function
if __name__ == "__main__":
    main()
