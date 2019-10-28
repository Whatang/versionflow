import os
import subprocess
import configparser
from contextlib import contextmanager
import six

import attr
import click
import git
import gitflow.core
import gitflow.branches
import setuptools_scm
import pkg_resources

VERSION = "0.3.0"

GITFLOW_RELEASE = u"release"
GITFLOW_HOTFIX = u"hotfix"
BV_PATCH = u"patch"
BV_MINOR = u"minor"
BV_MAJOR = u"major"
BV_SECTION = u"bumpversion"
BV_EXEC = u"bumpversion"
BV_CURRENT_VER_OPTION = u"current_version"
BV_NEW_VER_OPTION = u"new_version"
START_VERSION = u"0.0.0"
DEFAULT_BV_FILE = u".versionflow"


class VersionFlowError(Exception):
    def __str__(self):
        """
        Use the docstring for the error class as the error message.
        """
        return self.__doc__


class NoRepo(VersionFlowError):
    """Not a git repo."""


class DirtyRepo(VersionFlowError):
    """git repo is dirty."""


class NoGitFlow(VersionFlowError):
    """Not a git flow repo."""


class NoBumpVersion(VersionFlowError):
    """bumpversion not initalised."""


class BumpNotInGit(VersionFlowError):
    """bumpversion config not added to git repo."""


class GetBumpVersionError(VersionFlowError):
    """Could not retrieve the version from the bumpversion config."""


class GetNextBumpVersionError(VersionFlowError):
    """Could not determine the next version from bumpversion."""


class SetNextBumpVersionError(VersionFlowError):
    """Could not set the next version with bumpversion."""


class NoVersionTags(VersionFlowError):
    """Could not get version number from repository tags."""


class BadVersionTags(VersionFlowError):
    """Versions in bumpversion and git tags do not match."""


class VersionTagOnWrongBranch(VersionFlowError):
    """The last version tag is not on the master branch."""


class AlreadyReleasing(VersionFlowError):
    """There is already a release in progress."""


class GitError(VersionFlowError):
    """Error executing git commands."""


@contextmanager
def gitflow_context(*args, **kwargs):
    gflow = gitflow.core.GitFlow(*args, **kwargs)
    try:
        yield gflow
    finally:
        gflow.repo.close()


@contextmanager
def git_context(*args, **kwargs):
    repo = git.Repo(*args, **kwargs)
    try:
        yield repo
    finally:
        repo.close()


@contextmanager
def init_git_context(*args, **kwargs):
    repo = git.Repo.init(*args, **kwargs)
    try:
        yield repo
    finally:
        repo.close()


@attr.s
class Config(object):
    repo_dir = attr.ib(default=lambda: os.path.abspath(os.getcwd()))
    bumpversion_config = attr.ib(default=DEFAULT_BV_FILE)

    @contextmanager
    def get_git_context(self, create):
        click.echo("Checking if this is a clean git repo...")
        try:
            with git_context(self.repo_dir) as repo:
                click.echo("- Confirmed that this is a git repo")
                if repo.is_dirty():
                    raise DirtyRepo()
                else:
                    click.echo("- git repo is clean")
                yield repo
        except git.InvalidGitRepositoryError:
            if create:
                with init_git_context(self.repo_dir) as repo:
                    click.echo("- Initialised this directory as a git repo")
                    yield repo
            else:
                raise NoRepo()

    @contextmanager
    def get_gitflow_context(self, create):
        click.echo("Checking if this is a git flow repo...")
        with gitflow_context() as gflow:
            if gflow.is_initialized():
                click.echo("- Confirmed that this is a git flow repo")
            elif create:
                click.echo("- Initialising a git flow repo...")
                gflow.init()
                click.echo("- Initialised this directory as a git flow repo")
            else:
                raise NoGitFlow()
            yield gflow

    def check_bumpversion(self, create, repo):
        click.echo("Checking if bumpversion is initialised... ")
        try:
            # Check that the bumpversion config file is in the git repo
            bv_wrap = BumpVersionWrapper.from_existing(self.bumpversion_config)
            relpath = os.path.relpath(self.bumpversion_config)
            repo.active_branch.commit.tree / relpath
        except BumpVersionWrapper.NoBumpversionConfig:
            if create:
                bv_wrap = BumpVersionWrapper.initialize(
                    self.bumpversion_config)
                click.echo(
                    "- bumpversion initialised with current version set to "
                    + bv_wrap.current_version
                )
                repo.index.add([self.bumpversion_config])
                repo.index.commit("Add bumpversion config")
                return bv_wrap
            else:
                raise NoBumpVersion()
        except KeyError:
            if create:
                click.echo("- bumpversion config added to git repo")
                repo.index.add([self.bumpversion_config])
                repo.index.commit("Add bumpversion config")
            else:
                raise BumpNotInGit()
        click.echo("- bumpversion configured; version is at " +
                   bv_wrap.current_version)
        return bv_wrap

    @staticmethod
    def get_last_version():
        # Try to get version number from repository
        return setuptools_scm.get_version(
            version_scheme=_last_version, local_scheme=lambda v: ""
        )

    def check_version_tag(self, create, bv_wrapper, gf_wrapper):
        # Check that there is a version tag, and that it is
        # correct as per the bumpversion section
        click.echo("Checking version in repository tags...")
        try:
            version = self.get_last_version()
            click.echo("- Last tagged version is " + version)
            # Check if this version is on the master branch
            branches = gf_wrapper.repo.git.branch(
                "--contains", "tags/" + version
            ).splitlines()
            branches = [b.lstrip("*").strip() for b in branches]
            if "master" not in branches:
                raise VersionTagOnWrongBranch()
            # Check if the version tags match what we expect
            if version != bv_wrapper.current_version:
                raise BadVersionTags()
        except LookupError:
            if create:
                # set base version tags
                gf_wrapper.tag(bv_wrapper.current_version,
                               gf_wrapper.repo.heads.master)
                click.echo("- Base version tags set to " +
                           bv_wrapper.current_version)
            else:
                raise NoVersionTags()


def _set_curdir(unused_ctx, _, path):
    if not path:
        path = os.path.abspath(os.curdir)
    else:
        path = os.path.abspath(path)
        click.echo("Switching dir to " + path)
    os.chdir(path)
    return path


def _make_abs_path(unused_ctx, _, path):
    return os.path.abspath(path)


def _last_version(version):
    if str(version.tag) == "0.0":
        raise LookupError()
    return version.format_with("{tag}")


def get_current_scm_version(target_dir=None):
    try:
        old = os.path.abspath(os.getcwd())
        if target_dir is not None:
            os.chdir(target_dir)
        # Try to get version number from repository
        return setuptools_scm.get_version(
            version_scheme=_last_version, local_scheme="node-and-date"
        )
    finally:
        os.chdir(old)


def get_current_version(target_module, target_attribute="VERSION"):
    """Return the current version string for a client program or repo.

    `target_module` should be one which is in the root of the source
    control system, and contains an attribute named `target_attribute`.

    This will attempt to get a source control description of the current
    commit, or if none is available - likely because the program isn't
    being run from source control - will return the value of `target_attribute`
    in `target_module`.
    """
    # First try to get a description from the source control system
    if target_module is None:
        target_file = os.path.abspath(__file__)
        target_module = globals()
    else:
        target_file = os.path.abspath(target_module.__file__)
    target_dir = os.path.dirname(target_file)
    try:
        return get_current_scm_version(target_dir)
    except LookupError:
        # If that didn't work, just get a description
        return getattr(target_module, target_attribute)


@click.version_option(version=get_current_version(None, "VERSION"))
@click.group()
@click.option(
    "--repo-dir",
    metavar="PATH",
    is_eager=True,
    callback=_set_curdir,
    help="""Use the given PATH as the root of the versionflow repo. Defaults to the current directory.""",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "--config",
    callback=_make_abs_path,
    help="Use the given FILE as the versionflow configuration file. Defaults to .versionflow",
    type=click.Path(
        exists=False, file_okay=True, readable=True, writable=True, dir_okay=False
    ),
    default=DEFAULT_BV_FILE,
)
@click.pass_context
def cli(ctx, repo_dir, config):
    # Record configuration options
    ctx.obj = Config(repo_dir=repo_dir, bumpversion_config=config)


def _do_status(config, create):
    try:
        with VersionFlowRepo.create_checked(config, create):
            pass
    except VersionFlowError as exc:
        click.echo(str(exc), err=True)
        raise click.Abort()


@cli.command()
@click.pass_context
def describe(config):
    """Give the source control description of the current version.
    """
    click.echo(get_current_scm_version())


@cli.command()
@click.pass_obj
def init(config):
    """Initialise the repo to use versionflow."""
    _do_status(config, True)


@cli.command()
@click.pass_obj
def check(config):
    """Check if the repo state of this package is OK."""
    _do_status(config, False)


@attr.s
class VersionFlowRepo(object):
    config = attr.ib()
    gf_wrapper = attr.ib()
    bv_wrapper = attr.ib()

    @classmethod
    @contextmanager
    def create_checked(cls, config=None, create=False):
        if config is None:
            config = Config()
        # Check this is a clean git repo
        with config.get_git_context(create) as repo:
            # Check if git flow is initialised
            with config.get_gitflow_context(create) as gf_wrapper:
                # Check that there is a bumpversion section
                bv_wrapper = config.check_bumpversion(create, repo)
                # Check that there is a version tag, and that it is
                # correct as per the bumpversion section
                config.check_version_tag(create, bv_wrapper, gf_wrapper)
                yield cls(config, gf_wrapper, bv_wrapper)

    def process_action(self, versions, part):
        try:
            self.gitflow_start(versions)
            self.bv_wrapper.bump_and_commit(part)
            self.gitflow_end(versions)
            click.echo("New version is %s" % versions.new_version)
        except git.GitCommandError as exc:
            self._git_failure("Failed to do the release", exc)

    @staticmethod
    def _git_failure(message, exc):
        click.echo(message, err=True)
        click.echo(
            "{command} returned status {status}".format(
                command=exc.command, status=exc.status
            ),
            err=True,
        )
        click.echo(exc.stdout, err=True)
        click.echo(exc.stderr, err=True)
        raise GitError()

    def gitflow_start(self, versions):
        try:
            self.gf_wrapper.create(
                gitflow.branches.ReleaseBranchManager.identifier,
                versions.new_version,
                None,
                False,
            )
        except gitflow.branches.BranchTypeExistsError:
            raise AlreadyReleasing()

    def gitflow_end(self, versions):
        self.gf_wrapper.finish(
            gitflow.branches.ReleaseBranchManager.identifier,
            versions.new_version,
            False,
            False,
            False,
            True,
            tagging_info={"message": versions.new_version},
        )


def _do_version(config, level):
    try:
        with VersionFlowProcessor.from_config(config, level, GITFLOW_RELEASE) as proc:
            proc.process()
    except VersionFlowError as exc:
        click.echo(str(exc), err=True)
        raise click.Abort()


@cli.command()
@click.pass_obj
def patch(config):
    """Create a release with the patch number bumped."""
    _do_version(config, BV_PATCH)


@cli.command()
@click.pass_obj
def minor(config):
    """Create a release with the minor number bumped."""
    _do_version(config, BV_MINOR)


@cli.command()
@click.pass_obj
def major(config):
    """Create a release with the major number bumped."""
    _do_version(config, BV_MAJOR)


@attr.s
class VersionFlowProcessor(object):
    vf_repo = attr.ib()
    part = attr.ib(validator=attr.validators.in_(
        [BV_PATCH, BV_MINOR, BV_MAJOR]))
    flow_type = attr.ib(
        validator=attr.validators.in_([GITFLOW_RELEASE, GITFLOW_HOTFIX])
    )

    @classmethod
    @contextmanager
    def from_config(cls, config, part, flow_type):
        with VersionFlowRepo.create_checked(config, False) as vf_repo:
            yield cls(vf_repo=vf_repo, part=part, flow_type=flow_type)

    def process(self):
        versions = Versions.from_bumpversion(
            self.vf_repo.bv_wrapper, self.part)
        self.vf_repo.process_action(versions, self.part)


@attr.s
class BumpVersionWrapper(object):
    config_file = attr.ib()
    parsed_config = attr.ib()
    current_version = attr.ib()

    class NoBumpversionConfig(RuntimeError):
        pass

    @classmethod
    def from_existing(cls, bumpversion_config):
        if not os.path.exists(bumpversion_config):
            raise cls.NoBumpversionConfig()
        parsed_config = configparser.ConfigParser()
        parsed_config.read(bumpversion_config)
        if not parsed_config.has_section(BV_SECTION):
            raise cls.NoBumpversionConfig()
        try:
            current_version = parsed_config.get(
                BV_SECTION, BV_CURRENT_VER_OPTION)
        except (configparser.NoSectionError, configparser.NoOptionError):
            raise cls.NoBumpversionConfig()
        return cls(bumpversion_config, parsed_config, current_version)

    @classmethod
    def initialize(cls, bumpversion_config):
        config_parser = configparser.ConfigParser()
        if os.path.exists(bumpversion_config):
            config_parser.read(bumpversion_config)
        if not config_parser.has_section(BV_SECTION):
            config_parser.add_section(BV_SECTION)
        if not config_parser.has_option(BV_SECTION, BV_CURRENT_VER_OPTION):
            config_parser.set(BV_SECTION, BV_CURRENT_VER_OPTION, START_VERSION)
        config_parser.write(open(bumpversion_config, "w"))
        return cls(bumpversion_config, config_parser, START_VERSION)

    def bump_and_commit(self, part):
        try:
            self._run_bumpversion(["--commit", part])
        except subprocess.CalledProcessError as exc:
            # Handle bumpversion failures
            click.echo(
                "Failed to bump the version number in the release", err=True)
            click.echo(exc.output, err=True)
            raise SetNextBumpVersionError()

    def get_new_version(self, part):
        bv_output = self._run_bumpversion(["--list", part, "--dry-run"])
        new_version = None
        for line in bv_output.splitlines():
            if line.startswith(BV_NEW_VER_OPTION + "="):
                new_version = line.strip().split("=")[-1]
        # What if we can't find new version?
        if new_version is None:
            click.echo("Failed to get next version number", err=True)
            raise GetNextBumpVersionError()
        return new_version

    def _run_bumpversion(self, bv_args, **subprocess_kw_args):
        if six.PY3 and "encoding" not in subprocess_kw_args:
            subprocess_kw_args["encoding"] = "utf-8"
        return subprocess.check_output(
            [BV_EXEC] + ["--config-file", self.config_file] + bv_args,
            stderr=subprocess.STDOUT,
            **subprocess_kw_args
        )


@attr.s
class Versions(object):
    current_version = attr.ib()
    new_version = attr.ib()

    @classmethod
    def from_bumpversion(cls, bv_wrapper, part):
        """Get the current and next version from bumpversion."""
        try:
            return cls(bv_wrapper.current_version, bv_wrapper.get_new_version(part))
        except subprocess.CalledProcessError as exc:
            # Handle bumpversion failures
            click.echo("Failed to get version numbers", err=True)
            click.echo(exc.output, err=True)
            raise GetBumpVersionError()


if __name__ == "__main__":
    cli()  # pylint:disable=no-value-for-parameter
