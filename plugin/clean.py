from army.api.command import parser, group, command, option, argument
from army.api.debugtools import print_stack
from army.api.log import log
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
    config = ctx.parent.config
    
    # load project
    project = ctx.parent.project
    if project is None:
        print(f"no project found", sys.stderr)
        exit(1)
    
    # get target config
    target = ctx.parent.target
    target_name = ctx.parent.target_name
    if target is None:
        print(f"no target specified", file=sys.stderr)
        exit(1)
    
    if target is not None:
        folder = os.path.join('output', target_name)
        if os.path.exists(folder)==True:
            shutil.rmtree(folder)
        print(f"target '{target_name}' cleaned")
    
    else:
        folder = 'output'
        
        if os.path.exists('output')==True:
            shutil.rmtree('output')
    
        print(f"cleaned")
