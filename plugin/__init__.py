from army.api.command import get_army_parser
from army.api.profile import Profile
from army.api.schema import  Optional, Choice

parser = get_army_parser()
if parser.find_group("build") is None:
    parser.add_group(name="build", help="Build Commands", chain=True)

# add target validator
Profile._schema = {
    **Profile._schema,
    Optional('arch'): {
        'name': str,
        'cpu': str,
        'family': str,
        Optional('package'): str,
        Optional('version'): str
    },
    
    Optional('target'): {
        Optional('pre'): [str],
        Optional('definition'): str,
        Optional('post'): [str],
        Optional('elf'): str,
    }
} 


import clean
import compile
