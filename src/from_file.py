
SHORT_VERSION_PY_COMMENT = """
# This file was generated by 'versioneer.py' (@VERSIONEER-VERSION@) from
# revision-control system data, or from the parent directory name of an
# unpacked source archive. Distribution tarballs contain a pre-generated copy
# of this file.

"""

SHORT_VERSION_PY_TRAILER = """
def get_versions(default={}, verbose=False):
    return versions
def get_version():
    return version_string_template % versions
"""

DEFAULT = {"version": "unknown", "full": "unknown"}

def versions_from_file(filename):
    versions = {}
    try:
        f = open(filename)
    except EnvironmentError:
        return versions
    for line in f.readlines():
        mo = re.match("version_version = '([^']+)'", line)
        if mo:
            versions["version"] = mo.group(1)
        mo = re.match("version_full = '([^']+)'", line)
        if mo:
            versions["full"] = mo.group(1)
    f.close()
    return versions

def build_short_version_py(versions):
    out = []
    out.append(SHORT_VERSION_PY_COMMENT)
    out.append("versions = ")
    out.append(repr(versions))
    out.append("\n\n")
    out.append(SHORT_VERSION_PY_TRAILER)
    return "".join(out)

