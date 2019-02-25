import os
import subprocess

import attr
import bumpversion
import click
import pkg_resources
import setuptools_scm
import git

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


@attr.s
class Config(object):
    repo_dir = attr.ib()
    bumpversion_config = attr.ib()

    def bumpversion(self, bv_args, **subprocess_kw_args):
        return subprocess.check_output(
            ["bumpversion"] + bv_args + [self.bumpversion_config],
            stderr=subprocess.STDOUT,
            **subprocess_kw_args)


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
@click.pass_obj
def init(config):
    "Initialise the package to use versionflow."
    # TODO: create an initialisation command
    pass


@cli.command()
@click.pass_obj
def patch(config):
    "Create a release with the patch number bumped."
    Processor.from_config(config, "patch", GITFLOW_RELEASE).process()


@cli.command()
@click.pass_obj
def minor(config):
    "Create a release with the minor number bumped."
    Processor.from_config(config, "minor", GITFLOW_RELEASE).process()


@cli.command()
@click.pass_obj
def major(config):
    "Create a release with the major number bumped."
    Processor.from_config(config, "major", GITFLOW_RELEASE).process()


@attr.s
class Processor(object):
    repo = attr.ib()
    config = attr.ib()
    part = attr.ib(validator=attr.validators.in_(["patch", "minor", "major"]))
    flow_type = attr.ib(validator=attr.validators.in_(
        [GITFLOW_RELEASE, GITFLOW_HOTFIX]))

    @classmethod
    def from_config(cls, config, part, flow_type):
        try:
            return cls(repo=git.Repo(), config=config, part=part, flow_type=flow_type)
        except git.InvalidGitRepositoryError:
            click.echo("No git repo here", err=False)
            raise click.Abort()

    def process(self):
        versions = Versions.from_bumpversion(self.config, self.part)
        self._gitflow_start(versions)
        self._bump_and_commit()
        self._gitflow_end(versions)

    def _bump_and_commit(self):
        try:
            self.config.bumpversion(["--commit", self.part])
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
                self.repo.git.flow(self.flow_type, "finish",
                                   versions.new_version,
                                   "--message="+versions.release_merge_message(),
                                   "--force_delete",
                                   "--tag="+versions.release_version_string(),
                                   )
        except git.GitCommandError as exc:
            self._git_failure("Failed to complete the release", exc)


@attr.s
class Versions(object):
    current_version = attr.ib()
    new_version = attr.ib()

    @classmethod
    def from_bumpversion(cls, config, part):
        """Get the current and next version from bumpversion.
        """
        try:
            bv_output = config.bumpversion(
                ["--list", part, "--dry-run"])
            current_version = None
            new_version = None
            for line in bv_output.splitlines():
                if line.startswith("current_version="):
                    current_version = line.strip().split("=")[-1]
                elif line.startswith("new_version="):
                    new_version = line.strip().split("=")[-1]
            # What if we can't find both current and new version?
            if current_version is None:
                click.echo("Failed to get current version number", err=True)
                raise click.Abort()
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
