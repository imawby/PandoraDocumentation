#!/usr/bin/env python3

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
# - PandoraMonitoring
# - LibTorch
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
CXX_STANDARD = "17"

# LibTorch / DL specific
LINUX_URL = "https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-2.5.0%2Bcpu.zip"
MAC_URL = "https://download.pytorch.org/libtorch/cpu/libtorch-macos-1.9.0.zip"
MAC_ARM_URL = "https://download.pytorch.org/libtorch/cpu/libtorch-macos-arm64-2.3.1.zip"

# Determine the platform we are building on
PRE_BUILT_LIBTORCH = LINUX_URL

# If we are on Mac, we need to use the Mac version of LibTorch, and if we are on
# an ARM-based Mac, we need to use the ARM version of LibTorch.
if platform.system() == "Darwin" and platform.processor() == "arm":
    PRE_BUILT_LIBTORCH = MAC_ARM_URL
elif platform.system() == "Darwin":
    PRE_BUILT_LIBTORCH = MAC_URL

# Get the correct install path...
# gcc installs to build/install/lib64/..., but clang installs to build/install/lib/...
# Pick the most appropriate one based on the platform...but alert the user to check if it is correct.
LIB_INSTALL_PATH = "lib64" if platform.system() == "Linux" else "lib"

# The list of required packages for the build
REQUIRED_PACKAGES = [
    ("cmake", ["cmake", "--version"]),
    ("ninja", ["ninja", "--version"]),
    ("git", ["git", "--version"]),
    ("curl", ["curl", "--version"]),
    ("python3", ["python3", "--version"]),
    ("tar", ["tar", "--version"]),
]
BUILD_GEN = "-GNinja"


def run_command(
    args,
    command,
    message,
    error_message,
    exit_on_error=False,
    silent=False,
    cwd=None,
) -> None:
    command_string = command if isinstance(command, str) else " ".join(command)

    if args.verbose:
        print(f"Full command: {command_string}")

    if message:
        print(message)

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
        print(f"{error_message}: {e}")
        if exit_on_error:
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

    # DL dependency source options (DL itself is mandatory).
    parser.add_argument(
        "-d",
        "--download_libtorch",
        action="store_true",
        help="Download LibTorch from PyTorch (default if no source is specified).",
        default=True,
    )
    parser.add_argument(
        "-I",
        "--prebuilt_libtorch",
        help="Path to a pre-built LibTorch folder",
        default="",
    )
    parser.add_argument(
        "-L",
        "--larsoft_libtorch",
        action="store_true",
        help="Use the version of LibTorch provided by LArSoft (if available).",
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

    # Show the help message if no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    # Validate argument combinations for a predictable user experience.
    # DL support is mandatory: default to download if no source is selected.
    if (
        not args.prebuilt_libtorch
        and not args.larsoft_libtorch
        and not args.download_libtorch
    ):
        print("No LibTorch source specified, defaulting to --download-libtorch.")
        args.download_libtorch = True

    torch_source_count = (
        int(bool(args.download_libtorch))
        + int(bool(args.prebuilt_libtorch))
        + int(bool(args.larsoft_libtorch))
    )
    if torch_source_count > 1:
        parser.error(
            "Choose only one LibTorch source: --download-libtorch, --prebuilt-libtorch, or --larsoft-libtorch."
        )

    if args.build_near_detector:
        args.download_data = "dunend"

    return args


def clone_command(repo: str, git_flags: str = "") -> list[str]:
    command = ["git", "clone", repo]
    if git_flags:
        command.extend(shlex.split(git_flags))
    return command


def clone_repo(args, repo, command, cwd=None) -> None:
    if os.path.exists(f"{args.output}/{repo}"):
        print(f"{repo} already exists, skipping...")
        return

    run_command(
        args,
        command,
        f"Cloning {repo}...",
        f"Failed to clone {repo}",
        exit_on_error=True,
        cwd=cwd,
    )


def get_code(args) -> None:
    core_repos = [
        ("PandoraSDK", SDK),
        ("PandoraPFA", PFA),
        ("PandoraMonitoring", MONITORING),
        ("LArContent", LARCONTENT),
        ("LArMachineLearningData", MACHINELEARNING),
    ]
    for name, url in core_repos:
        clone_repo(args, name, clone_command(url), cwd=args.output)

    lar_reco_dir = "LArReco" if not args.build_near_detector else "LArRecoND"
    lar_reco_repo = LARRECO if not args.build_near_detector else LARRECOND
    clone_repo(args, lar_reco_dir, clone_command(lar_reco_repo), cwd=args.output)

    clone_repo(
        args,
        "Eigen3",
        f"curl -L {EIGEN} --output {args.output}/eigen.tar.gz",
        cwd=args.output,
    )

    # Work out if we need to get some form of LibTorch...
    # We can either download it or use a pre-built version.
    if args.download_libtorch:
        clone_repo(
            args,
            "libtorch",
            f"curl -L {PRE_BUILT_LIBTORCH} --output {args.output}/libtorch.zip",
            cwd=args.output,
        )
    elif args.prebuilt_libtorch:
        print(f"Using pre-built LibTorch from: {args.prebuilt_libtorch}")
    elif args.larsoft_libtorch:
        print("Using LArSoft-provided LibTorch (if available).")


def build_repo(args, target_repo: str, build_command: str) -> None:
    build_dir = f"{args.output}/{target_repo}/build"

    if os.path.exists(f"{args.output}/{target_repo}/build") and args.force:
        run_command(
            args,
            ["rm", "-rf", build_dir],
            f"Removing existing build directory for {target_repo}...",
            f"Failed to remove existing build directory for {target_repo}",
            exit_on_error=True,
        )

    if os.path.exists(build_dir):
        print(f"Build directory for {target_repo} already exists, skipping...")
        return

    print(f"Building {target_repo}...")
    os.makedirs(build_dir, exist_ok=True)
    print(f"Creating build directory for {target_repo}...")

    run_command(
        args,
        build_command,
        f"Running build command for {target_repo}...",
        f"Failed to build {target_repo}",
        exit_on_error=True,
        cwd=build_dir,
    )

    run_command(
        args,
        ["ninja", "install"],
        f"Running install command for {target_repo}...",
        f"Failed to install {target_repo}",
        exit_on_error=True,
        cwd=build_dir,
    )


def prepare_archives(args) -> None:
    """Extract downloaded archive artifacts if present."""
    if os.path.exists(f"{args.output}/eigen.tar.gz"):
        run_command(
            args,
            ["tar", "-xzf", f"{args.output}/eigen.tar.gz", "-C", args.output],
            "Extracting Eigen...",
            "Failed to extract Eigen",
            exit_on_error=True,
        )

        candidates = sorted(glob.glob(f"{args.output}/eigen-*"))
        if not candidates:
            print("Failed to locate extracted Eigen directory")
            sys.exit(1)
        run_command(
            args,
            ["mv", candidates[0], f"{args.output}/Eigen3"],
            "Moving Eigen...",
            "Failed to rename Eigen",
            exit_on_error=True,
        )
        run_command(
            args,
            ["rm", "-f", f"{args.output}/eigen.tar.gz"],
            "Removing Eigen archive...",
            "Failed to remove Eigen archive",
            exit_on_error=True,
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
            exit_on_error=True,
        )
        run_command(
            args,
            ["rm", "-f", f"{args.output}/libtorch.zip"],
            "Removing LibTorch archive...",
            "Failed to remove LibTorch archive",
            exit_on_error=True,
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
        f"-DPandoraSDK_DIR={args.output}/PandoraSDK/build/install/{LIB_INSTALL_PATH}/cmake/PandoraSDK"
    )
    pandora_monitoring = f"-DPANDORA_MONITORING=ON -DPandoraMonitoring_DIR={args.output}/PandoraMonitoring/build/install/{LIB_INSTALL_PATH}/cmake/PandoraMonitoring"
    eigen_flag = f"-DEigen3_DIR={args.output}/Eigen3/share/eigen3/cmake/"
    larcontent_flag = (
        f"-DLArContent_DIR={args.output}/LArContent/build/install/{LIB_INSTALL_PATH}/cmake/LArContent"
    )
    cmake_prefix_torch = ""
    if args.download_libtorch:
        cmake_prefix_torch = f'-DCMAKE_PREFIX_PATH="{args.output}/libtorch"'
    elif args.prebuilt_libtorch:
        cmake_prefix_torch = f'-DCMAKE_PREFIX_PATH="{args.prebuilt_libtorch}"'
    elif args.larsoft_libtorch:
        # Respect environment-provided LibTorch setup in LArSoft contexts.
        cmake_prefix_torch = ""

    return {
        "cmake_module_path": cmake_module_path,
        "root_cmake_module_path": root_cmake_module_path,
        "pandora_sdk": pandora_sdk,
        "pandora_monitoring": pandora_monitoring,
        "eigen_flag": eigen_flag,
        "larcontent_flag": larcontent_flag,
        "cmake_prefix_torch": cmake_prefix_torch,
    }


def download_ml_data_if_needed(args) -> None:
    """Download machine-learning data only when absent."""
    if os.path.exists(f"{args.output}/LArMachineLearningData/PandoraMVAData"):
        print("PandoraMVAData already exists, skipping...")
        return

    ml_download_commands = f"export MY_TEST_AREA={args.output};"
    download_target = "dune lbl" if args.download_data == "dune" else args.download_data
    ml_download_commands = f"{ml_download_commands} bash {args.output}/LArMachineLearningData/download.sh {download_target}"

    run_command(
        args,
        ml_download_commands,
        "Downloading ML data...",
        "Failed to download ML data",
        exit_on_error=True,
    )


def build_code(args) -> None:
    # Double check the environment is setup correctly
    # We dont want to go via cetbuildtools, so unset it
    if "CETBUILDTOOLS_VERSION" in os.environ:
        print("Unsetting CETBUILDTOOLS_VERSION, to avoid cetbuildtools")
        os.environ.pop("CETBUILDTOOLS_VERSION")

    prepare_archives(args)

    common_flags = build_common_flags(args)
    cmake_module_path = common_flags["cmake_module_path"]
    root_cmake_module_path = common_flags["root_cmake_module_path"]
    pandora_sdk = common_flags["pandora_sdk"]
    pandora_monitoring = common_flags["pandora_monitoring"]
    eigen_flag = common_flags["eigen_flag"]
    larcontent_flag = common_flags["larcontent_flag"]
    cmake_prefix_torch = common_flags["cmake_prefix_torch"]

    libtorch_flag = "-DPANDORA_LIBTORCH=ON"
    dl_content_flag = f"-DLArDLContent_DIR={args.output}/LArContent/build/install/{LIB_INSTALL_PATH}/cmake/LArDLContent"
    lar_content_build_flags = f"{root_cmake_module_path} {pandora_sdk} {pandora_monitoring} {eigen_flag} {libtorch_flag} {cmake_prefix_torch}".strip()
    lar_reco_build_flags = f"{root_cmake_module_path} {pandora_sdk} {pandora_monitoring} {larcontent_flag} {libtorch_flag} {cmake_prefix_torch} {dl_content_flag}".strip()

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

    # Monitoring is always built in this script.
    build_repo(
        args,
        "PandoraMonitoring",
        f"cmake {root_cmake_module_path} {pandora_sdk} {BUILD_GEN} ..",
    )

    # And finally, the main event, the LArContent and LArReco
    lar_reco_dir = "LArReco" if not args.build_near_detector else "LArRecoND"
    build_targets = [
        ("LArContent", lar_content_build_flags),
        (lar_reco_dir, lar_reco_build_flags),
    ]
    for target, flags in build_targets:
        build_repo(args, target, f"cmake {flags} {BUILD_GEN} ..")


def main() -> None:
    args = parse_args()
    cwd = os.getcwd()
    changed_to_output = False

    # Check we have the required packages installed
    for package, command in REQUIRED_PACKAGES:
        run_command(
            args,
            command,
            "",
            f"Could not find {package}",
            exit_on_error=True,
            silent=True,
        )

    # Check if the output directory exists, if not create it and any parent directories
    if not os.path.exists(args.output):
        os.makedirs(args.output)

    # Change to the output directory when it exists.
    if os.path.exists(args.output):
        os.chdir(args.output)
        changed_to_output = True
    else:
        print(f"Output directory does not exist: {args.output}")
        sys.exit(1)

    # Get the code from the repositories...
    print("Cloning required repositories...")
    get_code(args)
    print("Cloning complete...")

    # If we are only cloning, then exit here
    if args.clone_only:
        sys.exit(0)

    # Then build the code
    print("Starting to build...")
    build_code(args)
    print("Build complete...")

    # Return to the original directory
    if changed_to_output:
        os.chdir(cwd)

    # Everything is done!
    # Alert the user on the next steps...
    print(f"Only the ML data for {args.download_data.upper()} has been downloaded...")
    print("Download other data files as required.")
    print("The script for this lives is:")
    print(f"{args.output}/LArMachineLearningData/download.sh")

    print("All done! Pandora is now built and ready to use.")
    print("Setup any environment variables to locate configs as needed.")
    print("Re-build things using ninja in the relevant build folder.")


# Run the main function
if __name__ == "__main__":
    main()
