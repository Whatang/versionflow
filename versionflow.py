import os
import subprocess
import ConfigParser

import attr
import click
import pkg_resources
import setuptools_scm
import git
import gitflow.core
import gitflow.branches

try:
    # Try to get version number from repository
    VERSION = setuptools_scm.get_version()
except LookupError:
    # Not in repo, so try to get version number from pkg_resources
    try:
        VERSION = pkg_resources.get_distribution("versionflow").version
    except pkg_resources.DistributionNotFound:
        # Not installed?
        VERSION = "Unknown"

GITFLOW_RELEASE = "release"
GITFLOW_HOTFIX = "hotfix"
BUMPVERSION_PATCH = "patch"
BUMPVERSION_MINOR = "minor"
BUMPVERSION_MAJOR = "major"
BV_SECTION = "bumpversion"
BV_CURRENT_VER_OPTION = "current_version"
BV_NEW_VER_OPTION = "new_version"
START_VERSION = "0.0.1"


@attr.s
class Config(object):
    repo_dir = attr.ib()
    bumpversion_config = attr.ib()


def _set_curdir(ctx, _, path):
    if not path:
        path = os.path.abspath(os.curdir)
    else:
        path = os.path.abspath(path)
        click.echo("Switching dir to " + path)
    os.chdir(path)
    return path


def _make_abs_path(ctx, _, path):
    return os.path.abspath(path)


@click.version_option(version=VERSION)
@click.group()
@click.option('--repo-dir', metavar="PATH", is_eager=True,
              callback=_set_curdir,
              # TODO: add help
              type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--bumpversion-config',
              callback=_make_abs_path,
              # TODO: add help
              type=click.Path(exists=False, file_okay=True,
                              readable=True, writable=True, dir_okay=False),
              default="setup.cfg")
@click.pass_context
def cli(ctx, repo_dir, bumpversion_config):
    # Record configuration options
    ctx.obj = Config(repo_dir=repo_dir, bumpversion_config=bumpversion_config)


@cli.command()
@click.option("--create", "-c", is_flag=True)
@click.pass_obj
def init(config, create):
    """Initialise the package to use versionflow."""
    RepoStatusHandler.from_config(config, create).process()


@cli.command()
@click.pass_obj
def check(config):
    """Check if the versionflow state of this package is OK."""
    RepoStatusHandler.from_config(config, False).process()


@attr.s
class RepoStatus(object):
    repo = attr.ib()
    gf_wrapper = attr.ib()
    bv_wrapper = attr.ib()


@attr.s
class RepoStatusHandler(object):
    config = attr.ib()
    create = attr.ib(default=False)

    class NoRepo(RuntimeError):
        pass

    class DirtyRepo(RuntimeError):
        pass

    class NoGitFlow(RuntimeError):
        pass

    class BadBumpVersion(RuntimeError):
        pass

    class NoVersionTags(RuntimeError):
        pass

    class BadVersionTags(RuntimeError):
        pass

    @classmethod
    def from_config(cls, config, create):
        return cls(config=config, create=create)

    def process(self):
        # Check this is a clean git repo
        repo = self._check_git()
        # Check if git flow is initialised
        gf_wrapper = self._check_gitflow(repo)
        # Check that there is a bumpversion section
        bv_wrapper = self._check_bumpversion()
        # Check that there is a version tag, and that it is
        # correct as per the bumpversion section
        self._check_version_tag(repo, bv_wrapper, gf_wrapper)
        return RepoStatus(repo, gf_wrapper, bv_wrapper)

    def _check_git(self):
        click.echo("Checking if this is a clean git repo...")
        try:
            repo = git.Repo(self.config.repo_dir)
            click.echo("- Confirmed that this is a git repo")
            if repo.is_dirty():
                click.echo("- git repo is dirty", err=True)
                raise self.DirtyRepo()
            else:
                click.echo("- git repo is clean")
        except git.InvalidGitRepositoryError:
            if self.create:
                repo = git.Repo.init(self.config.repo_dir)
                click.echo("- Initialised this directory as a git repo")
            else:
                click.echo("- Not a git repo", err=True)
                raise self.NoRepo()
        return repo

    def _check_gitflow(self, repo):
        click.echo("Checking if this is a git flow repo...")
        gf = gitflow.core.GitFlow()
        if gf.is_initialized():
            click.echo("- Confirmed that this is a git flow repo")
        elif self.create:
            click.echo("- Initialising a git flow repo...")
            gf.init()
            click.echo("- Initialised this directory as a git flow repo")
        else:
            click.echo("- Not a git flow repo", err=True)
            raise self.NoGitFlow()
        return gf

    def _check_bumpversion(self):
        click.echo("Checking if bumpversion is initialised...")
        try:
            bv = BumpVersion.from_existing(self.config)
            click.echo(
                "- bumpversion configured; version is at " +
                bv.current_version)
        except BumpVersion.NoBumpversionConfig:
            if self.create:
                bv = BumpVersion.initialize(self.config)
                click.echo(
                    "- bumpversion configured with current version set to " +
                    bv.current_version)
            else:
                click.echo("- bumpversion not initalised!", err=True)
                raise self.BadBumpVersion()
        return bv

    def _check_version_tag(self, repo, bv_wrapper, gf_wrapper):
        # Check that there is a version tag, and that it is
        # correct as per the bumpversion section
        click.echo("Checking version in repository tags...")
        try:
            # Try to get version number from repository
            def last_version(version):
                if str(version.tag) == '0.0':
                    raise LookupError()
                return version.format_with("{tag}")
            version = setuptools_scm.get_version(
                version_scheme=last_version,
                local_scheme=lambda v: "")
            click.echo("- Last tagged version is " + version)
            # Check if the version tags match what we expect
            if version != bv_wrapper.current_version:
                raise self.BadVersionTags()
        except LookupError:
            if self.create:
                # set base version tags
                gf_wrapper.tag(bv_wrapper.current_version, "HEAD")
            else:
                click.echo(
                    "- Could not get version number from repository tags")
                raise self.NoVersionTags()


@cli.command()
@click.pass_obj
def patch(config):
    """Create a release with the patch number bumped."""
    Processor.from_config(config, "patch", GITFLOW_RELEASE).process()


@cli.command()
@click.pass_obj
def minor(config):
    """Create a release with the minor number bumped."""
    Processor.from_config(config, "minor", GITFLOW_RELEASE).process()


@cli.command()
@click.pass_obj
def major(config):
    """Create a release with the major number bumped."""
    Processor.from_config(config, "major", GITFLOW_RELEASE).process()


@attr.s
class Processor(object):
    repo_status = attr.ib()
    config = attr.ib()
    bv_wrapper = attr.ib()
    part = attr.ib(validator=attr.validators.in_(["patch", "minor", "major"]))
    flow_type = attr.ib(validator=attr.validators.in_(
        [GITFLOW_RELEASE, GITFLOW_HOTFIX]))

    @classmethod
    def from_config(cls, config, part, flow_type):
        repo_status = RepoStatusHandler.from_config(
            config, False).process()
        return cls(
            repo_status=repo_status,
            config=config,
            part=part,
            flow_type=flow_type)

    def process(self):
        versions = Versions.from_bumpversion(
            self.repo_status.bv_wrapper, self.part)
        self._gitflow_start(versions)
        self._bump_and_commit()
        self._gitflow_end(versions)

    def _bump_and_commit(self):
        try:
            self.bv_wrapper.run_bumpversion(["--commit", self.part])
        except subprocess.CalledProcessError as exc:
            # Handle bumpversion failures
            click.echo(
                "Failed to bump the version number in the release", err=True)
            click.echo(exc.output, err=True)
            raise click.Abort()

    @staticmethod
    def _git_failure(message, exc):
        click.echo(message, err=True)
        click.echo("{command} returned status {status}".format(
            command=exc.command, status=exc.status), err=True)
        click.echo(exc.stdout, err=True)
        click.echo(exc.stderr, err=True)
        raise click.Abort()

    def _gitflow_start(self, versions):
        try:
            self.repo_status.gf_wrapper.create(
                gitflow.branches.ReleaseBranchManager.identifier,
                versions.new_version)
        except git.GitCommandError as exc:
            self._git_failure("Failed to start the release", exc)

    def _gitflow_end(self, versions):
        try:
            self.repo_status.gf_wrapper.finish(
                gitflow.branches.ReleaseBranchManager.identifier,
                versions.new_version,
                False,
                False,
                False,
                True,
                tagging_info={})
        except git.GitCommandError as exc:
            self._git_failure("Failed to complete the release", exc)


@attr.s
class BumpVersion(object):
    config_file = attr.ib()
    parsed_config = attr.ib()
    current_version = attr.ib()

    class NoBumpversionConfig(RuntimeError):
        pass

    @classmethod
    def from_existing(cls, vf_config):
        if (not os.path.exists(vf_config.bumpversion_config)):
            raise BumpVersion.NoBumpversionConfig()
        parsed_config = ConfigParser.ConfigParser()
        parsed_config.read(vf_config.bumpversion_config)
        if not parsed_config.has_section(BV_SECTION):
            raise BumpVersion.NoBumpversionConfig()
        try:
            current_version = parsed_config.get(
                BV_SECTION, BV_CURRENT_VER_OPTION)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            raise BumpVersion.NoBumpversionConfig()
        return BumpVersion(
            vf_config.bumpversion_config,
            parsed_config,
            current_version)

    @classmethod
    def initialize(cls, vf_config):
        config_parser = ConfigParser.ConfigParser()
        if os.path.exists(vf_config.bumpversion_config):
            config_parser.read(vf_config.bumpversion_config)
        if not config_parser.has_section(BV_SECTION):
            config_parser.add_section(BV_SECTION)
        if not config_parser.has_option(BV_SECTION, BV_CURRENT_VER_OPTION):
            config_parser.set(BV_SECTION, BV_CURRENT_VER_OPTION, START_VERSION)
        config_parser.write(open(vf_config.bumpversion_config, "w"))
        return BumpVersion(
            vf_config.bumpversion_config,
            config_parser,
            START_VERSION)

    def run_bumpversion(self, bv_args, **subprocess_kw_args):
        return subprocess.check_output(
            ["bumpversion"] + bv_args + [self.config_file],
            stderr=subprocess.STDOUT,
            **subprocess_kw_args)


@attr.s
class Versions(object):
    current_version = attr.ib()
    new_version = attr.ib()

    @classmethod
    def from_bumpversion(cls, bv_wrapper, part):
        """Get the current and next version from bumpversion."""
        try:
            current_version = bv_wrapper.current_version
            bv_output = bv_wrapper.run_bumpversion(
                ["--list", part, "--dry-run"])
            new_version = None
            for line in bv_output.splitlines():
                if line.startswith(BV_NEW_VER_OPTION + "="):
                    new_version = line.strip().split("=")[-1]
            # What if we can't find new version?
            if new_version is None:
                click.echo("Failed to get next version number", err=True)
                raise click.Abort()
            return cls(current_version, new_version)
        except subprocess.CalledProcessError as exc:
            # Handle bumpversion failures
            click.echo("Failed to get version numbers", err=True)
            click.echo(exc.output, err=True)
            raise click.Abort()

    def release_version_string(self):
        return "v{version}".format(version=self.new_version)

    def release_merge_message(self):
        return "Merging release/{version}".format(version=self.new_version)


if __name__ == "__main__":
    cli()  # pylint:disable=no-value-for-parameter
