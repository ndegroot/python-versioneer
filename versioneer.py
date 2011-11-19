#! /usr/bin/python

"""versioneer.py

(like a rocketeer, but for versions)

* https://github.com/warner/python-versioneer
* Brian Warner
* License: Public Domain

This file helps distutils-based projects manage their version number by just
creating version-control tags.

For developers who work from a VCS-generated tree (e.g. 'git clone' etc),
each 'setup.py version', 'setup.py build', 'setup.py sdist' will compute a
version number by asking your version-control tool about the current
checkout. The version number will be written into a generated _version.py
file of your choosing, where it can be included by your __init__.py

For users who work from a VCS-generated tarball (e.g. 'git archive'), it will
compute a version number by looking at the name of the directory created when
te tarball is unpacked. This conventionally includes both the name of the
project and a version number.

For users who work from a tarball built by 'setup.py sdist', it will get a
version number from a previously-generated _version.py file.

As a result, loading code directly from the source tree will not result in a
real version. If you want real versions from VCS trees (where you frequently
update from the upstream repository, or do new development), you will need to
do a 'setup.py version' after each update, and load code from the build/
directory.

You need to provide this code with a few configuration values:

 versionfile_source:
    A project-relative pathname into which the generated version strings
    should be written. This is usually a _version.py next to your project's
    main __init__.py file. If your project uses src/myproject/__init__.py,
    this should be 'src/myproject/_version.py'. This file should be checked
    in to your VCS as usual: the copy created below by 'setup.py
    update_files' will include code that parses expanded VCS keywords in
    generated tarballs. The 'build' and 'sdist' commands will replace it with
    a copy that has just the calculated version string.

 versionfile_build:
    Like versionfile_source, but relative to the build directory instead of
    the source directory. These will differ when your setup.py uses
    'package_dir='. If you have package_dir={'myproject': 'src/myproject'},
    then you will probably have versionfile_build='myproject/_version.py' and
    versionfile_source='src/myproject/_version.py'.

 tag_prefix: a string, like 'PROJECTNAME-', which appears at the start of all
             VCS tags. If your tags look like 'myproject-1.2.0', then you
             should use tag_prefix='myproject-'. If you use unprefixed tags
             like '1.2.0', this should be an empty string.

 parentdir_prefix: a string, frequently the same as tag_prefix, which
                   appears at the start of all unpacked tarball filenames. If
                   your tarball unpacks into 'myproject-1.2.0', this should
                   be 'myproject-'.

To use it:

 1: include this file in the top level of your project
 2: make the following changes to the top of your setup.py:
     import versioneer
     versioneer.versionfile_source = 'src/myproject/_version.py'
     versioneer.versionfile_build = 'myproject/_version.py'
     versioneer.tag_prefix = '' # tags are like 1.2.0
     versioneer.parentdir_prefix = 'myproject-' # dirname like 'myproject-1.2.0'
 3: add the following arguments to the setup() call in your setup.py:
     version=versioneer.get_version(),
     cmdclass=versioneer.get_cmdclass(),
 4: run 'setup.py update_files', which will create _version.py, and will
    append the following to your __init__.py:
     from _version import __version__
 5: modify your MANIFEST.in to include versioneer.py
 6: add both versioneer.py and the generated _version.py to your VCS
"""

import os, sys, re
from distutils.core import Command
from distutils.command.sdist import sdist as _sdist
from distutils.command.build import build as _build

versionfile_source = None
versionfile_build = None
tag_prefix = None
parentdir_prefix = None

class NoVersionError(Exception):
    pass

VCS = "git"
LONG_VERSION_PY = '''
# This file helps to compute a version number in source trees obtained from
# git-archive tarball (such as those provided by githubs download-from-tag
# feature). Distribution tarballs (build by setup.py sdist) and build
# directories (produced by setup.py build) will contain a much shorter file
# that just contains the computed version number.

# This file is released into the public domain.

# these strings will be replaced by git during git-archive
git_refnames = "%(DOLLAR)sFormat:%%d%(DOLLAR)s"
git_full = "%(DOLLAR)sFormat:%%H%(DOLLAR)s"


import subprocess

def run_command(args, cwd=None, verbose=False):
    try:
        p = subprocess.Popen(list(args), stdout=subprocess.PIPE, cwd=cwd)
    except EnvironmentError, e:
        if verbose:
            print "unable to run %%s" %% args[0]
            print e
        return None
    stdout = p.communicate()[0].strip()
    if p.returncode != 0:
        if verbose:
            print "unable to run %%s (error)" %% args[0]
        return None
    return stdout


import re
import os.path

def get_expanded_variables(versionfile_source):
    # the code embedded in _version.py can just fetch the value of these
    # variables. When used from setup.py, we don't want to import
    # _version.py, so we do it with a regexp instead. This function is not
    # used from _version.py.
    variables = {}
    try:
        for line in open(versionfile_source,"r").readlines():
            if line.strip().startswith("git_refnames ="):
                mo = re.search(r'=\s*"(.*)"', line)
                if mo:
                    variables["refnames"] = mo.group(1)
            if line.strip().startswith("git_full ="):
                mo = re.search(r'=\s*"(.*)"', line)
                if mo:
                    variables["full"] = mo.group(1)
    except EnvironmentError:
        pass
    return variables

def versions_from_expanded_variables(variables, tag_prefix):
    refnames = variables["refnames"].strip()
    if refnames.startswith("$Format"):
        return {} # unexpanded, so not in an unpacked git-archive tarball
    refs = set([r.strip() for r in refnames.strip("()").split(",")])
    refs.discard("HEAD") ; refs.discard("master")
    for ref in reversed(sorted(refs)):
        if ref.startswith(tag_prefix):
            r = ref[len(tag_prefix):]
            if re.search(r'\d', r):
                # git's %%d expansion behaves like git log --decorate=short
                # and strips out the refs/heads/ and refs/tags/ prefixes that
                # would let us distinguish between branches and tags. By
                # ignoring refnames without digits, we filter out many common
                # branch names like "release" and "stabilization".
                return { "version": r,
                         "full": variables["full"].strip() }
    # no suitable tags, so we use the full revision id
    return { "version": variables["full"].strip(),
             "full": variables["full"].strip() }

def versions_from_vcs(tag_prefix, verbose=False):
    # this runs 'git' from the directory that contains this file. That either
    # means someone ran a setup.py command (and this code is in
    # versioneer.py, thus the containing directory is the root of the source
    # tree), or someone ran a project-specific entry point (and this code is
    # in _version.py, thus the containing directory is somewhere deeper in
    # the source tree). This only gets called if the git-archive 'subst'
    # variables were *not* expanded, and _version.py hasn't already been
    # rewritten with a short version string, meaning we're inside a checked
    # out source tree.

    try:
        source_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # some py2exe/bbfreeze/non-CPython implementations don't do __file__
        return {} # not always correct
    stdout = run_command(["git", "describe",
                          "--tags", "--dirty", "--always"], cwd=source_dir)
    if stdout is None:
        return {}
    if not stdout.startswith(tag_prefix):
        if verbose:
            print "tag '%%s' doesn't start with prefix '%%s'" %% \
                  (stdout, tag_prefix)
        return {}
    tag = stdout[len(tag_prefix):]
    stdout = run_command(["git", "rev-parse", "HEAD"], cwd=source_dir)
    if stdout is None:
        return {}
    full = stdout.strip()
    if tag.endswith("-dirty"):
        full += "-dirty"
    return {"version": tag, "full": full}


tag_prefix = "%(TAG_PREFIX)s"
def get_versions():
    variables = { "refnames": git_refnames, "full": git_full }
    ver = versions_from_expanded_variables(variables, tag_prefix)
    if not ver:
        ver = versions_from_vcs(tag_prefix)
    if not ver:
        ver = {"version": "unknown", "full": ""}
    return ver

'''


import subprocess

def run_command(args, cwd=None, verbose=False):
    try:
        p = subprocess.Popen(list(args), stdout=subprocess.PIPE, cwd=cwd)
    except EnvironmentError, e:
        if verbose:
            print "unable to run %s" % args[0]
            print e
        return None
    stdout = p.communicate()[0].strip()
    if p.returncode != 0:
        if verbose:
            print "unable to run %s (error)" % args[0]
        return None
    return stdout


import re
import os.path

def get_expanded_variables(versionfile_source):
    # the code embedded in _version.py can just fetch the value of these
    # variables. When used from setup.py, we don't want to import
    # _version.py, so we do it with a regexp instead. This function is not
    # used from _version.py.
    variables = {}
    try:
        for line in open(versionfile_source,"r").readlines():
            if line.strip().startswith("git_refnames ="):
                mo = re.search(r'=\s*"(.*)"', line)
                if mo:
                    variables["refnames"] = mo.group(1)
            if line.strip().startswith("git_full ="):
                mo = re.search(r'=\s*"(.*)"', line)
                if mo:
                    variables["full"] = mo.group(1)
    except EnvironmentError:
        pass
    return variables

def versions_from_expanded_variables(variables, tag_prefix):
    refnames = variables["refnames"].strip()
    if refnames.startswith("$Format"):
        return {} # unexpanded, so not in an unpacked git-archive tarball
    refs = set([r.strip() for r in refnames.strip("()").split(",")])
    refs.discard("HEAD") ; refs.discard("master")
    for ref in reversed(sorted(refs)):
        if ref.startswith(tag_prefix):
            r = ref[len(tag_prefix):]
            if re.search(r'\d', r):
                # git's %d expansion behaves like git log --decorate=short
                # and strips out the refs/heads/ and refs/tags/ prefixes that
                # would let us distinguish between branches and tags. By
                # ignoring refnames without digits, we filter out many common
                # branch names like "release" and "stabilization".
                return { "version": r,
                         "full": variables["full"].strip() }
    # no suitable tags, so we use the full revision id
    return { "version": variables["full"].strip(),
             "full": variables["full"].strip() }

def versions_from_vcs(tag_prefix, verbose=False):
    # this runs 'git' from the directory that contains this file. That either
    # means someone ran a setup.py command (and this code is in
    # versioneer.py, thus the containing directory is the root of the source
    # tree), or someone ran a project-specific entry point (and this code is
    # in _version.py, thus the containing directory is somewhere deeper in
    # the source tree). This only gets called if the git-archive 'subst'
    # variables were *not* expanded, and _version.py hasn't already been
    # rewritten with a short version string, meaning we're inside a checked
    # out source tree.

    try:
        source_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # some py2exe/bbfreeze/non-CPython implementations don't do __file__
        return {} # not always correct
    stdout = run_command(["git", "describe",
                          "--tags", "--dirty", "--always"], cwd=source_dir)
    if stdout is None:
        return {}
    if not stdout.startswith(tag_prefix):
        if verbose:
            print "tag '%s' doesn't start with prefix '%s'" % \
                  (stdout, tag_prefix)
        return {}
    tag = stdout[len(tag_prefix):]
    stdout = run_command(["git", "rev-parse", "HEAD"], cwd=source_dir)
    if stdout is None:
        return {}
    full = stdout.strip()
    if tag.endswith("-dirty"):
        full += "-dirty"
    return {"version": tag, "full": full}


def do_vcs_install(versionfile_source, ipy):
    run_command(["git", "add", "versioneer.py"])
    run_command(["git", "add", versionfile_source])
    run_command(["git", "add", ipy])
    present = False
    try:
        f = open(".gitattributes", "r")
        for line in f.readlines():
            if line.strip().startswith(versionfile_source):
                if "export-subst" in line.strip().split()[1:]:
                    present = True
        f.close()
    except EnvironmentError:
        pass    
    if not present:
        f = open(".gitattributes", "a+")
        f.write("%s export-subst\n" % versionfile_source)
        f.close()
        run_command(["git", "add", ".gitattributes"])
    

SHORT_VERSION_PY = """
# This file was generated by 'versioneer.py' from revision-control system
# data, or from the parent directory name of an unpacked source archive.
# Distribution tarballs contain a pre-generated copy of this file.

version_version = '%(version)s'
version_full = '%(full)s'
def get_versions():
    return {'version': version_version, 'full': version_full}

"""

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
    return versions

def write_to_version_file(filename, versions):
    f = open(filename, "w")
    f.write(SHORT_VERSION_PY % versions)
    f.close()
    print "set %s to '%s'" % (filename, versions["version"])

def versions_from_parentdir(tag_prefix, parentdir_prefix, verbose):
    # try a couple different things to handle py2exe, bbfreeze, and
    # non-CPython implementations. Since this code lives in versioneer.py, we
    # either expect __file__ to be versioneer.py (kept in the root of the
    # source tree), or for sys.argv[0] to be setup.py (also in the root),
    # such that its parent is the root of the unpacked tarball, which
    # conventionally includes both a project name and a version string.
    try:
        me = __file__
    except NameError:
        me = sys.argv[0]
    me = os.path.abspath(me)
    dirname = os.path.basename(os.path.dirname(me))
    if not dirname.startswith(parentdir_prefix):
        if verbose:
            print "dirname '%s' doesn't start with prefix '%s'" % \
                  (dirname, parentdir_prefix)
        return None
    return {"version": dirname[len(parentdir_prefix):], "full": ""}

def get_best_versions(versionfile, tag_prefix, parentdir_prefix,
                      default={}, verbose=False):
    # returns dict with two keys: 'version' and 'full'
    #
    # extract version from first of _version.py, 'git describe', parentdir.
    # This is meant to work for developers using a source checkout, for users
    # of a tarball created by 'setup.py sdist', and for users of a
    # tarball/zipball created by 'git archive' or github's download-from-tag
    # feature.

    variables = get_expanded_variables(versionfile_source)
    if variables:
        ver = versions_from_expanded_variables(variables, tag_prefix)
        if ver:
            if verbose: print "got version from expanded variable", ver
            return ver

    ver = versions_from_file(versionfile)
    if ver:
        if verbose: print "got version from file %s" % versionfile, ver
        return ver

    ver = versions_from_vcs(tag_prefix, verbose)
    if ver:
        if verbose: print "got version from git", ver
        return ver

    ver = versions_from_parentdir(tag_prefix, parentdir_prefix, verbose)
    if ver:
        if verbose: print "got version from parentdir", ver
        return ver

    ver = default
    if ver:
        if verbose: print "got version from default", ver
        return ver

    raise NoVersionError("Unable to compute version at all")

def get_versions(verbose=False):
    assert versionfile_source is not None, "please set versioneer.versionfile_source"
    assert tag_prefix is not None, "please set versioneer.tag_prefix"
    assert parentdir_prefix is not None, "please set versioneer.parentdir_prefix"
    return get_best_versions(versionfile_source, tag_prefix, parentdir_prefix,
                             verbose=verbose)
def get_version(verbose=False):
    return get_versions(verbose).get("version", "unknown")

class cmd_version(Command):
    description = "report generated version string"
    user_options = []
    boolean_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        ver = get_version(verbose=True)
        print "Version is currently:", ver


class cmd_build(_build):
    def run(self):
        versions = get_versions(verbose=True)
        _build.run(self)
        # now locate _version.py in the new build/ directory and replace it
        # with an updated value
        target_versionfile = os.path.join(self.build_lib, versionfile_build)
        print "UPDATING", target_versionfile
        os.unlink(target_versionfile)
        f = open(target_versionfile, "w")
        f.write(SHORT_VERSION_PY % versions)
        f.close()

class cmd_sdist(_sdist):
    def run(self):
        versions = get_versions(verbose=True)
        self._versioneer_generated_versions = versions
        # unless we update this, the command will keep using the old version
        self.distribution.metadata.version = versions["version"]
        return _sdist.run(self)

    def make_release_tree(self, base_dir, files):
        _sdist.make_release_tree(self, base_dir, files)
        # now locate _version.py in the new base_dir directory (remembering
        # that it may be a hardlink) and replace it with an updated value
        target_versionfile = os.path.join(base_dir, versionfile_source)
        print "UPDATING", target_versionfile
        os.unlink(target_versionfile)
        f = open(target_versionfile, "w")
        f.write(SHORT_VERSION_PY % self._versioneer_generated_versions)
        f.close()

INIT_PY_SNIPPET = """
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

"""

class cmd_update_files(Command):
    description = "modify __init__.py and create _version.py"
    user_options = []
    boolean_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        ipy = os.path.join(os.path.dirname(versionfile_source), "__init__.py")
        print " creating %s" % versionfile_source
        f = open(versionfile_source, "w")
        f.write(LONG_VERSION_PY % {"DOLLAR": "$", "TAG_PREFIX": tag_prefix})
        f.close()
        try:
            old = open(ipy, "r").read()
        except EnvironmentError:
            old = ""
        if INIT_PY_SNIPPET not in old:
            print " appending to %s" % ipy
            f = open(ipy, "a")
            f.write(INIT_PY_SNIPPET)
            f.close()
        else:
            print " %s unmodified" % ipy
        do_vcs_install(versionfile_source, ipy)

def get_cmdclass():
    return {'version': cmd_version,
            'update_files': cmd_update_files,
            'build': cmd_build,
            'sdist': cmd_sdist,
            }
