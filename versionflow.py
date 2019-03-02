import os
import subprocess

import attr
import bumpversion

import click
import pkg_resources
import setuptools_scm
import git
import ConfigParser

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
class RepoStatusHandler(object):
    config = attr.ib()
    create = attr.ib(default=False)

    @classmethod
    def from_config(cls, config, create):
        return cls(config=config, create=create)

    def process(self):
        # Check this is a git repo
        repo = self._check_git()
        # Is it clean?
        self._check_clean(repo)
        # Check if git flow is initialised
        self._check_gitflow(repo)
        # Check that there is a bumpversion section
        bv_wrapper = self._check_bumpversion()
        # Check that there is a version tag, and that it is
        # correct as per the bumpversion section
        self._check_version_tag(repo, bv_wrapper)

    def _check_git(self):
        click.echo("Checking if this is a git repo...")
        try:
            repo = git.Repo(self.config.repo_dir)
            click.echo("- Confirmed that this is a git repo")
        except git.InvalidGitRepositoryError:
            if self.create:
                repo = git.Repo.init(self.config.repo_dir)
                click.echo("- Initialised this directory as a git repo")
            else:
                click.echo("- Not a git repo", err=True)
                raise click.Abort()
        return repo

    def _check_clean(self, repo):
        if repo.is_dirty():
            click.echo("git repo is dirty", err=True)
            raise click.Abort()
        else:
            click.echo("git repo is clean")

    def _check_gitflow(self, repo):
        click.echo("Checking if this is a git flow repo...")
        try:
            repo.git.flow("config")
            click.echo("- Confirmed that this is a git flow repo")
        except git.GitCommandError:
            if self.create:
                repo.git.flow("init")
                click.echo("- Initialised this directory as a git flow repo")
            else:
                click.echo("- Not a git flow repo", err=True)
                raise click.Abort()

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
                    "- bumpversion configured with current version set to" +
                    bv.current_version)
            else:
                click.echo("- bumpversion not initalised!", err=True)
                raise click.Abort()
        return bv

    def _check_version_tag(self, repo, bv_wrapper):
        # TODO: Check that there is a version tag, and that it is
        # correct as per the bumpversion section
        pass


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
    repo = attr.ib()
    config = attr.ib()
    bv_wrapper = attr.ib()
    part = attr.ib(validator=attr.validators.in_(["patch", "minor", "major"]))
    flow_type = attr.ib(validator=attr.validators.in_(
        [GITFLOW_RELEASE, GITFLOW_HOTFIX]))

    @classmethod
    def from_config(cls, config, part, flow_type):
        try:
            repo = git.Repo(config.repo_dir)
        except git.InvalidGitRepositoryError:
            click.echo("No git repo here", err=False)
            raise click.Abort()
        if repo.is_dirty():
            click.echo(
                "versionflow can only run on a clean repo - -- check "
                "everything in first!",
                err=True)
            raise click.Abort()
        try:
            bv_wrapper = BumpVersion.from_existing(config)
        except BumpVersion.NoBumpversionConfig:
            click.echo("Could not determine bumpversion configuration",
                       err=True)
            raise click.Abort()
        return cls(
            repo=repo,
            config=config,
            bv_wrapper=bv_wrapper,
            part=part,
            flow_type=flow_type)

    def process(self):
        versions = Versions.from_bumpversion(
            self.bv_wrapper, self.part)
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
            self.repo.git.flow(self.flow_type, "start", versions.new_version)
        except git.GitCommandError as exc:
            self._git_failure("Failed to start the release", exc)

    def _gitflow_end(self, versions):
        try:
            with self.repo.git.custom_environment(GIT_MERGE_AUTOEDIT="no"):
                self.repo.git.flow(
                    self.flow_type,
                    "finish",
                    versions.new_version,
                    "--message=" +
                    versions.release_merge_message(),
                    "--force_delete",
                    "--tag=" +
                    versions.release_version_string(),
                )
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
            config_parser.set(BV_SECTION, BV_CURRENT_VER_OPTION, "0.0.0")
        config_parser.write(vf_config.bumpversion_config)
        return BumpVersion(
            vf_config.bumpversion_config,
            config_parser,
            "0.0.0")

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
