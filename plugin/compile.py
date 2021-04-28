from army.api.command import parser, group, command, option, argument
from army.api.debugtools import print_stack
from army.api.log import log, get_log_level
from army.api.package import load_project_packages, load_installed_package
from army.api.project import load_project
import shutil
import os
import sys
from cmake import _program
import subprocess

#TODO add https://github.com/HBehrens/puncover

def to_relative_path(path):
    home = os.path.expanduser("~")
    abspath = os.path.abspath(path)
    if abspath.startswith(home):
        path = abspath.replace(home, "~", 1)
    cwd = os.path.abspath(os.path.expanduser(os.getcwd()))
    if abspath.startswith(cwd):
        path = os.path.relpath(abspath, cwd)
    return path
 
tools_path = os.path.expanduser(to_relative_path(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))))

@parser
@group(name="build")
@command(name='compile', help='Build package')
@option(name='debug', shortcut='d', help='Build with debug options', flag=True, default=False)
@option(name='instrument', shortcut='i', help='Build release with debug informations', flag=True, default=False)
@option(name='jobs', shortcut='j', value='COUNT', help='Number of parallel builds', type=int, default=1)
def compile(ctx, debug, instrument, jobs, **kwargs):
    log.info(f"compile")

    # load configuration
    config = ctx.config

    # load profile
    profile = ctx.profile
    
    # load project
    project = ctx.project
    if project is None:
        print(f"no project found", sys.stderr)
        exit(1)
        # 
    cmake_opts = []
    make_opts = []

    # set code build path
    output_path = 'output'
    
    # set home directory
    cmake_opts.append("-H.")

    # load dependencies
    try:
        dependencies = load_project_packages(project)
        log.debug(f"dependencies: {dependencies}")
    except Exception as e:
        print_stack()
        print(f"{e}", file=sys.stderr)
        clean_exit()

    # add toolchain
    try:
        toolchain_name = profile.data["/tools/toolchain/name"]        
        toolchain_definition = profile.data["/tools/toolchain/definition"]
        toolchain_path = profile.data["/tools/toolchain/path"]
        cmake_opts.append(f"-DCMAKE_TOOLCHAIN_FILE='{toolchain_definition}'")
    except Exception as e:
        print_stack()
        log.error(e)
        print("No toolchain definition provided by profile", file=sys.stderr)
        exit(1)

    # get arch from profile
    arch, arch_package = get_arch(profile, project, dependencies)

    # get target from profile
    target = get_target(profile)

    if debug==True and instrument==True:
        print(f"debug and instrument can not be used simultaneously", file=sys.stderr)
        exit(1)
         
    if debug==True:
        cmake_opts.append("-DCMAKE_BUILD_TYPE=Debug")
    elif instrument==True:
        cmake_opts.append("-DCMAKE_BUILD_TYPE=RelWithDebInfo")
    else:
        cmake_opts.append("-DCMAKE_BUILD_TYPE=Release")
 
    if get_log_level()!="fatal":
        cmake_opts.append("-DCMAKE_VERBOSE_MAKEFILE=ON")
    else:
        cmake_opts.append("-DCMAKE_VERBOSE_MAKEFILE=OFF")

    cmake_opts.append("-DCMAKE_COLOR_MAKEFILE=ON")
 
    #  Suppress developer warnings. Suppress warnings that are meant for the author of the CMakeLists.txt files
    cmake_opts.append("-Wno-dev")

    # search for toolchain binaries
    locate_tools(profile)

    # set build path
    if arch.mpu is None:
        build_path = os.path.join(output_path, arch.cpu)
        print(f"Build using toolchain {toolchain_name} for arch {arch.cpu}")
    else:
        build_path = os.path.join(output_path, arch.mpu)
        print(f"Build using toolchain {toolchain_name} for mpu {arch.mpu}")
        
    log.info(f"build_path: {build_path}")
    cmake_opts.append(f"-B{build_path}")
 
    # for ccache
    os.putenv("CCACHE_LOGFILE", os.path.abspath(os.path.join(build_path, "ccache.log")))

    # add path
    os.putenv("tools_path", os.path.abspath(tools_path))
    os.putenv("toolchain_path", os.path.abspath(toolchain_path))
    os.putenv("project_path", os.path.abspath(os.getcwd()))
    
    os.putenv("c_path", profile.data['/tools/c/path'])
    os.putenv("cxx_path", profile.data['/tools/c++/path'])
    os.putenv("asm_path", profile.data['/tools/asm/path'])
    os.putenv("ar_path", profile.data['/tools/ar/path'])
    os.putenv("ld_path", profile.data['/tools/ld/path'])
    os.putenv("objcopy_path", profile.data['/tools/objcopy/path'])
    os.putenv("objdump_path", profile.data['/tools/objdump/path'])
    os.putenv("size_path", profile.data['/tools/size/path'])
    os.putenv("nm_path", profile.data['/tools/nm/path'])

    # add arch vars
    os.putenv("cpu", arch.cpu)
    os.putenv("mpu", arch.mpu)
    if arch_package is None:
        os.putenv("arch_package", "_")
    else:
        os.putenv("arch_package", arch_package.name)
    os.putenv("arch_path", arch.cpu_definition)
    
    try:
        log.info(f"cmake options: {' '.join(cmake_opts)}")
# 
        # create output folder
        os.makedirs(build_path, exist_ok=True)

        # add smake files
        add_cmake_files(build_path, dependencies, arch, arch_package, target)

        # TODO force rebuild elf file even if not changed
        # find ${PROJECT_PATH}/output -name "*.elf" -exec rm -f {} \; 2>/dev/null

        if get_log_level()=='debug':
            os.system("env")
            SystemExit(_program('cmake', ['--version']))

        # generate cmake files            
        res = SystemExit(_program('cmake', cmake_opts))
        if res.code>0:
            log.error(f"Build failed")
            exit(1)
    except Exception as e:
        print_stack()
        log.error(f"{e}")
        clean_exit()
 
 
    make_opts.append(f"-j{jobs}")
  
#     # enable color output
#     os.putenv("GCC_COLORS", 'error=01;31:warning=01;35:note=01;36:caret=01;32:locus=01:quote=01')

    cwd = os.getcwd()
    try: 
        log.info(f"make options: {' '.join(make_opts)}")
         
        # build now
        os.chdir(build_path)
        subprocess.check_call(['make']+make_opts)
    except Exception as e:
        print_stack()
        log.error(f"{e}")
        os.chdir(cwd)
        clean_exit()
 
    os.chdir(cwd)



def clean_exit():
#     # clean elf files to avoid uploading a wrong one
#     find ${PROJECT_PATH}/output -name "*.elf" -exec rm -f {} \; 2>/dev/null
#     
#     echo "Build failed" >&2
    exit(1)

def locate_tools(profile):
    tools = { 
        "c": "c compiler",
        "c++": "c++ compiler",
        "asm": "assembler compiler",
        "ld": "linker",
        "ar": "archive tool",
        "objcopy": "object file copy tool",
        "objdump": "object file content dump tool",
        "size": "object file size tool",
        "nm": "symbols export tool",
    }
    for tool, name in tools.items():
        try:
            tool_path = profile.data[f"/tools/{tool}/path"] 
            if os.path.exists(tool_path)==False:
                print(f"{tool_path}: path not found for {name}", file=sys.stderr)
                exit(1)
        except Exception as e:
            print_stack()
            log.error(e)
            print(f"No {name} defined", file=sys.stderr)
            exit(1)
# 
#     # search for eabi
#     arm_gcc_eabi = None
#     for folder in os.listdir(os.path.join(toolchain_path, arm_gcc_path, 'lib', 'gcc', 'arm-none-eabi')):
#         arm_gcc_eabi = folder
#     if arm_gcc_eabi is None:
#         print(f"gcc eabi not found inside '{toolchain_path}', check plugin installation", file=sys.stderr)
#         exit(1)
#     os.putenv('arm_gcc_eabi', arm_gcc_eabi)
    
def locate_cmake():
    global tools_path

    # search for gcc folder
    cmake_path = 'cmake'
    if os.path.exists(os.path.join(tools_path, cmake_path, 'bin', 'cmake'))==False:
        print(f"cmake was not found inside '{tools_path}', check plugin installation", file=sys.stderr)
        exit(1)
    os.putenv('cmake_path', cmake_path)
    
    return os.path.join(tools_path, cmake_path, 'bin', 'cmake')

def add_cmake_files(build_path, dependencies, arch, arch_package, target):
    global tools_path
#     # build list of includes
#     includes = get_cmake_target_includes(target)
#     includes += get_cmake_includes(dependencies)

    # copy army.cmake
    try:
        shutil.copy(os.path.join(os.path.expanduser(tools_path), "cmake", "army.cmake"), build_path)
    except Exception as e:
        print_stack()
        log.error(f"{e}")
        exit(1)
    
    with open(os.path.join(build_path, "army.cmake"), "a") as fa:
        print("\n# dependencies section definition", file=fa)
        
        with open(os.path.join(build_path, "dependencies.cmake"), "w") as fd:
            # add target
            print("\n# target definition", file=fa)
            if target is not None:
                print(f'include_army_package_file(_ {target["definition"]})', file=fd)

            for dependency in dependencies:
                if 'cmake' in dependency.definition:
                    print(f'set({dependency.name}_path "{dependency.path}")', file=fa)
                    print(f'set({dependency.name}_definition "{os.path.join(dependency.path, dependency.definition["cmake"])}")', file=fa)
                    print(f"include_army_package({dependency.name})", file=fd)

                    os.putenv(f"package_{dependency.name}_path", dependency.path)
                    os.putenv(f"package_{dependency.name}_definition", dependency.definition["cmake"])
                    
                log.info(f"Adding dependency: {dependency}")
            
            # add arch
            print("\n# arch definition", file=fa)
            if arch.mpu_definition is not None:
                if arch_package is None:
                    print(f'include_army_package_file(_ {arch.mpu_definition})', file=fd)
                else:
                    os.putenv(f"package_{arch_package.name}_path", arch_package.path)
                    print(f'include_army_package_file({arch_package.name} {arch.mpu_definition})', file=fd)

            
            
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

def get_target(profile):
    target = None
    
    if "target" in profile.data:
        target = profile.data["/target"]
    
    return target
