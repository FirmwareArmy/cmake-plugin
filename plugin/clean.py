from army.api.command import parser, group, command, option, argument
from army.api.debugtools import print_stack
from army.api.log import log
from army.api.package import load_project_packages, load_installed_package
from army.api.project import load_project
import os
import sys
import shutil

@parser
@group(name="build")
@command(name='clean', help='Clean project')
def clean(ctx, **kwargs):
    log.info(f"clean")

    # load configuration
    config = ctx.config

    # load profile
    profile = ctx.profile

    # set code build path
    output_path = 'output'

    # load project
    project = ctx.project
    if project is None:
        print(f"no project found", sys.stderr)
        exit(1)

    # load dependencies
    try:
        dependencies = load_project_packages(project)
        log.debug(f"dependencies: {dependencies}")
    except Exception as e:
        print_stack()
        print(f"{e}", file=sys.stderr)
        clean_exit()

    # get arch from profile
    arch, arch_package = get_arch(profile, project, dependencies)

    # set build path
    if arch.mpu is None:
        build_path = os.path.join(output_path, arch.cpu)
    else:
        build_path = os.path.join(output_path, arch.mpu)
        
    log.info(f"clean path: {build_path}")


    if os.path.exists(build_path)==True:
        shutil.rmtree(build_path)

    print(f"cleaned")

def get_arch(profile, project, dependencies):
    # add arch
    try:
        arch = profile.data["/arch"]
        arch_name = profile.data["/arch/name"]
    except Exception as e:
        print_stack()
        log.error(e)
        print("No arch definition provided by profile", file=sys.stderr)
        exit(1)
    
    if 'name' not in arch:
        print("Arch name missing", file=sys.stderr)
        exit(1)

    package = None
    res_package = None
    if 'package' in arch:
        if 'version' in arch:
            package_version = arch['version']
        else:
            package_version = 'latest'
        package_name = arch['package']
        package = load_installed_package(package_name, package_version)
        res_package = package
    
    if package is None:
        package = project
    
    # search arch in found package
    archs = package.archs
    arch = next(arch for arch in archs if arch.name==arch_name)
    if arch is None:
        print(f"Arch {arch_name} not found in {package}", file=sys.stderr)
        exit(1)
    
    return arch, res_package
