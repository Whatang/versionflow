import os
import subprocess

import attr
import bumpversion
import click
import pkg_resources
import setuptools_scm

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


@click.version_option(version=VERSION)
@click.group()
@click.option('--repo-dir', metavar="PATH",
              type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.pass_context
def cli(ctx, repo_dir):
    # Record configuration options
    ctx.obj = Config(repo_dir=repo_dir)


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
    Processor(config, "patch", GITFLOW_RELEASE).process()


@cli.command()
@click.pass_obj
def minor(config):
    "Create a release with the minor number bumped."
    Processor(config, "minor", GITFLOW_RELEASE).process()


@cli.command()
@click.pass_obj
def major(config):
    "Create a release with the major number bumped."
    Processor(config, "major", GITFLOW_RELEASE).process()


@attr.s
class Processor(object):
    config = attr.ib()
    part = attr.ib(validator=attr.validators.in_(["patch", "minor", "major"]))
    flow_type = attr.ib(validator=attr.validators.in_(
        [GITFLOW_RELEASE, GITFLOW_HOTFIX]))
    setup_cfg_path = attr.ib(default="setup.cfg")

    def process(self):
        if self.config.repo_dir:
            os.chdir(self.config.repo_dir)
        versions = Versions.from_bumpversion(self)
        self._gitflow_start(versions)
        self._bump_and_commit(versions)
        self._gitflow_end(versions)

    def bumpversion(self, bv_args, **subprocess_kw_args):
        return subprocess.check_output(
            ["bumpversion"] + bv_args + [self.setup_cfg_path],
            stderr=subprocess.STDOUT,
            **subprocess_kw_args)

    def _bump_and_commit(self, versions):
        try:
            self.bumpversion(["--commit", self.part])
        except subprocess.CalledProcessError as exc:
            # Handle bumpversion failures
            click.echo(
                "Failed to bump the version number in the release", err=True)
            click.echo(exc.output, err=True)
            raise click.Abort()

    def _gitflow_start(self, versions):
        try:
            self._gitflow(["start", versions.new_version])
        except subprocess.CalledProcessError as exc:
            # Handle gitflow failures
            click.echo("Failed to start the release", err=True)
            click.echo(exc.output, err=True)
            raise click.Abort()

    def _gitflow_end(self, versions):
        try:
            self._gitflow(
                ["finish",
                 "-m", "Merging release/{release_version}".format(
                     release_version=versions.new_version),
                 "--force_delete",
                 "--tag", "v{release_version}".format(
                     release_version=versions.new_version),
                 versions.new_version],
                env={"GIT_MERGE_AUTOEDIT": "no"})
        except subprocess.CalledProcessError as exc:
            # Handle gitflow failures
            click.echo("Failed to finish merging the release", err=True)
            click.echo(exc.output, err=True)
            raise click.Abort()

    def _gitflow(self, gf_args, **subprocess_kw_args):
        return subprocess.check_output(
            ["git", "flow", self.flow_type] + gf_args,
            stderr=subprocess.STDOUT,
            **subprocess_kw_args)


@attr.s
class Versions(object):
    current_version = attr.ib()
    new_version = attr.ib()

    @classmethod
    def from_bumpversion(cls, processor):
        """Get the current and next version from bumpversion.
        """
        try:
            bv_output = processor.bumpversion(
                ["--list", processor.part, "--dry-run"])
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


if __name__ == "__main__":
    cli()  # pylint:disable=no-value-for-parameter
