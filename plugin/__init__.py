from army.api.command import get_army_parser
from army.api.profile import Profile
from army.api.schema import Schema, String, VersionString, Optional, PackageString, Array, Dict, VariableDict, Variant, VersionRangeString, Boolean

parser = get_army_parser()
if parser.find_group("build") is None:
    parser.add_group(name="build", help="Build Commands", chain=True)

# add target validator
Profile._schema['arch'] = Optional(
        Dict({
            'name': String(),
            'package': Optional(String()),
            'version': Optional(String())
        })
    )

Profile._schema['target'] = Optional(
        Dict({
            'definition': String(),
            'elf': Optional(String()),
        })
    )


import clean
import compile
