from army.api.command import get_army_parser
from army.api.profile import Profile
from army.api.schema import Schema, String, VersionString, Optional, PackageString, Array, Dict, VariableDict, Variant, VersionRangeString, Boolean

parser = get_army_parser()
parser.add_group(name="build", help="Build Commands")

# add target validator
Profile._schema['arch'] = Optional(
        Dict({
            'cpu': String(),
            'mpu': String(),
            'definition': String()
        })
    )


import clean
import compile
