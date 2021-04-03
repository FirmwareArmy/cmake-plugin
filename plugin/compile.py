from army.api.command import parser, group, command, option, argument
from army.api.debugtools import print_stack
from army.api.log import log, get_log_level
from army.api.package import load_project_packages
from army.api.project import load_project
import tornado.template as template
import shutil
import os
import sys
from cmake import _program
import subprocess

#TODO add https://github.com/HBehrens/puncover

# def to_relative_path(path):
#     home = os.path.expanduser("~")
#     abspath = os.path.abspath(path)
#     if abspath.startswith(home):
#         path = abspath.replace(home, "~", 1)
#     cwd = os.path.abspath(os.path.expanduser(os.getcwd()))
#     if abspath.startswith(cwd):
#         path = os.path.relpath(abspath, cwd)
#     return path
# 
# toolchain_path = to_relative_path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
    
#     # get target config
#     target = ctx.parent.target
#     target_name = ctx.parent.target_name
#     if target is None:
#         print(f"no target specified", file=sys.stderr)
#         exit(1)
# 
    cmake_opts = []
    make_opts = []

    # set code build path
    output_path = 'output'
    
    # set home directory
    cmake_opts.append("-H.")
     
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

    # add arch
    try:
        arch_cpu = profile.data["/arch/cpu"]        
        arch_mpu = profile.data["/arch/mpu"]        
        arch_path = profile.data["/arch/definition"]
    except Exception as e:
        print_stack()
        log.error(e)
        print("No arch definition provided by profile", file=sys.stderr)
        exit(1)

    # set build path
    build_path = os.path.join(output_path, arch_mpu)
    log.info(f"build_path: {build_path}")
    cmake_opts.append(f"-B{build_path}")
 

    if debug==True and instrument==True:
        print(f"debug and instrument can not be used simultaneously", file=sys.stderr)
        exit(1)
         
    if debug==True:
        cmake_opts.append("-DCMAKE_BUILD_TYPE=Debug")
    elif instrument==True:
        cmake_opts.append("-DCMAKE_BUILD_TYPE=RelWithDebInfo")
    else:
        cmake_opts.append("-DCMAKE_BUILD_TYPE=Release")
 
    print(f"Build using toolchain {toolchain_name} for arch {arch_mpu}")
    if get_log_level()!="fatal":
        cmake_opts.append("-DCMAKE_VERBOSE_MAKEFILE=ON")
    else:
        cmake_opts.append("-DCMAKE_VERBOSE_MAKEFILE=OFF")

    cmake_opts.append("-DCMAKE_COLOR_MAKEFILE=ON")
 
    #  Suppress developer warnings. Suppress warnings that are meant for the author of the CMakeLists.txt files
    cmake_opts.append("-Wno-dev")
 
#     # load dependencies
#     try:
#         dependencies = load_project_packages(project, target_name)
#         log.debug(f"dependencies: {dependencies}")
#     except Exception as e:
#         print_stack()
#         print(f"{e}", file=sys.stderr)
#         clean_exit()
# 
    # search for toolchain binaries
    locate_tools(profile)
#     
#     # set build arch 
#     arch, arch_pkg = get_arch(config, target, dependencies)
#     log.debug(f"arch: {arch}")
#     os.putenv("LIBRARY_PATH", os.path.abspath(arch_pkg.path))
#     os.putenv('arch_path', os.path.abspath(os.path.join(arch_pkg.path, arch.definition)))
#     
    # for ccache
    os.putenv("CCACHE_LOGFILE", os.path.abspath(os.path.join(build_path, "ccache.log")))

    # add path
    os.putenv("toolchain_path", os.path.abspath(toolchain_path))
    os.putenv("project_path", os.path.abspath(os.getcwd()))
    
    os.putenv("c_path", profile.data['/tools/c/path'])
    os.putenv("cxx_path", profile.data['/tools/c++/path'])
    os.putenv("asm_path", profile.data['/tools/asm/path'])
    os.putenv("ar_path", profile.data['/tools/ar/path'])
    os.putenv("ld_path", profile.data['/tools/ld/path'])

    try:
        log.info(f"cmake options: {' '.join(cmake_opts)}")
# 
#         # add CMakeLists.txt
#         add_build_file(dependencies, target)
# 
        # create output folder
        os.makedirs(build_path, exist_ok=True)
# 
#     # TODO force rebuild elf file even if not changed
#     # find ${PROJECT_PATH}/output -name "*.elf" -exec rm -f {} \; 2>/dev/null
#             
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
        "ar": "archive tool"
    }
    for tool, name in tools.items():
        try:
            tool_path = profile.data["/tools/c/path"] 
            if os.path.exists(tool_path)==False:
                print(f"{tool_path}: path not found for {name}", file=sys.stderr)
                exit(1)
        except Exception as e:
            print_stack()
            log.error(e)
            print(f"No {name} defined", file=sys.stderr)
            exit(1)

#         
#     # search for gcc folder
#     arm_gcc_path = 'gcc'
#     if os.path.exists(os.path.join(toolchain_path, arm_gcc_path))==False:
#         print(f"gcc was not found inside '{toolchain_path}', check plugin installation", file=sys.stderr)
#         exit(1)
#     os.putenv('arm_gcc_path', arm_gcc_path)
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
    global toolchain_path

    # search for gcc folder
    cmake_path = 'cmake'
    if os.path.exists(os.path.join(toolchain_path, cmake_path, 'bin', 'cmake'))==False:
        print(f"cmake was not found inside '{toolchain_path}', check plugin installation", file=sys.stderr)
        exit(1)
    os.putenv('cmake_path', cmake_path)
    
    return os.path.join(toolchain_path, cmake_path, 'bin', 'cmake')

def get_arch(config, target, dependencies):
    target_arch = target.arch
    
    res = None
    found_dependency = None
    for dependency in dependencies:
        for arch in dependency.arch:
            if arch==target.arch:
                if found_dependency is not None:
                    log.error(f"arch '{arch}' redefinition from'{found_dependency[1].name}' in {dependency.name}")
                    exit(1)
                found_dependency = (dependency.arch[arch], dependency)
                if dependency.arch[arch].definition=="":
                    log.error(f"missing definition in arch '{arch}' from '{dependency.name}'")
                    exit(1)

    if found_dependency is None:
        print(f"no configuration available for arch '{target.arch}'", file=sys.stderr)
        exit(1)
    
    return found_dependency

def get_cmake_includes(dependencies):
    res = ""
    
    for dependency in dependencies:
        cmake = dependency.cmake
        if cmake:
            if cmake.include:
                library_path = os.path.abspath(dependency.path)
                res = f'{res}set(LIBRARY_PATH "{library_path}")\n'
                res = f"{res}include({os.path.join(library_path, cmake.include)})\n"
    return res

def get_cmake_target_includes(target):
    res = ""
    
    if target.definition:
        target_path = os.path.abspath(target.definition)
        res = f'{res}set(TARGET_PATH "{os.path.dirname(target_path)}")\n'
        res = f"{res}include({target_path})\n"
    return res

def add_build_file(dependencies, target):
    global toolchain_path
    
    # build list of includes
    includes = get_cmake_target_includes(target)
    includes += get_cmake_includes(dependencies)
    
    # write CMakeLists.txt from template
    try:
        loader = template.Loader(os.path.join(toolchain_path, 'template'), autoescape=None)
        cmakelists = loader.load("CMakeLists.txt").generate(
            includes=includes,
            project_path=os.path.abspath(os.getcwd())
        )
        with open("CMakeLists.txt", "w") as f:
            f.write(cmakelists.decode("utf-8"))
    except Exception as e:
        print_stack()
        log.error(f"{e}")
        exit(1)
        

