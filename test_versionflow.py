import contextlib
import cProfile
import os
import unittest

import click
import click.testing

import states_for_tests as state
import versionflow


@contextlib.contextmanager
def profile():
    cp = cProfile.Profile()
    cp.enable()
    try:
        yield
    finally:
        cp.disable()
        cp.print_stats("tottime")


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.runner = click.testing.CliRunner()
        self.test_args = []

    def process(self):
        raise NotImplementedError()

    def check_error(self, expected_error):
        """
        Check that the correct behaviour is followed for a bad repo state.

        expected_error is a subclass of VfStatusError, or an instance of some
        such subclass.

        This test runs the self.process() method of the test, then checks
        that versionflow exited with an error status, that it returned exit
        code 1, and that the text of the

        """
        # Run the init check
        result = self.process()
        self.assertIsInstance(result.exception, SystemExit)
        self.assertEqual(result.exit_code, 1)
        if not isinstance(expected_error, versionflow.VfStatusError):
            expected_error = expected_error()
        self.assert_(
            result.stdout.endswith(
                str(expected_error) +
                "\n" +
                "Aborted!\n"))

    def check_good_repo(self, expected_version=state.GOOD_VERSION):
        result = self.process()
        try:
            self.assertEqual(result.exit_code, 0)
            # It is a git repo.
            self.assert_(os.path.exists(".git"))
            with versionflow.git_context() as repo:
                # It is not dirty.
                self.assertFalse(repo.is_dirty())
                with versionflow.gitflow_context() as gf:
                    # It is a gitflow repo.
                    self.assert_(gf.is_initialized())
                    # Bumpversion version number present, in git
                    # repo, and matches git tag
                    self.assert_(os.path.exists(state.BV_CONFIG))
                    self.assert_(
                        repo.active_branch.commit.tree / state.BV_CONFIG)
                    bv = versionflow.BumpVersionWrapper.from_existing(
                        state.BV_CONFIG)
                    # - The version number is what we expect it to be.
                    self.assertEqual(bv.current_version, expected_version)
                    # TODO: The output is what we expect.
        except BaseException:
            print(result.stdout)
            raise


class SimpleCommand(BaseTest):
    command_args = []

    def process(self, *args):
        return self.runner.invoke(
            versionflow.cli,
            self.command_args +
            self.test_args)


class Test_Init(SimpleCommand):
    command_args = ["init"]

    @state.do_nothing
    def test_InitNoGit(self):
        self.check_good_repo(versionflow.START_VERSION)

    @state.make_git
    def test_InitJustGit(self):
        self.check_good_repo(versionflow.START_VERSION)

    @state.dirty_empty_git
    def test_InitDirtyEmptyGit(self):
        self.check_error(versionflow.DirtyRepo)

    @state.dirty_git
    def test_InitDirtyGit(self):
        self.check_error(versionflow.DirtyRepo)

    @state.clean_git
    def test_InitCleanGit(self):
        self.check_good_repo(versionflow.START_VERSION)

    @state.empty_gitflow
    def test_InitEmptyGitflow(self):
        self.check_good_repo(versionflow.START_VERSION)

    @state.dirty_empty_gitflow
    def test_InitDirtyEmptyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

    @state.dirty_gitflow
    def test_InitDirtyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

    @state.clean_gitflow
    def test_InitCleanGitflow(self):
        self.check_good_repo(versionflow.START_VERSION)

    @state.just_bump
    def test_InitJustBump(self):
        self.check_good_repo()

    @state.git_with_untracked_bump
    def test_InitEmptyGitAndBump(self):
        self.check_good_repo()

    @state.git_with_dirty_bump
    def test_InitGitAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

    @state.git_with_bump
    def test_InitGitAndBump(self):
        self.check_good_repo()

    @state.gitflow_with_untracked_bump
    def test_InitEmptyGitFlowAndBump(self):
        self.check_good_repo()

    @state.gitflow_with_dirty_bump
    def test_InitGitFlowAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

    @state.gitflow_with_bump
    def test_InitGitFlowAndBump(self):
        self.check_good_repo()

    @state.empty_bad_tag_and_bump
    def test_InitEmptyBadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

    @state.bad_tag_and_bump
    def test_InitBadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

    @state.good_base_repo
    def test_InitRepoAlreadyGood(self):
        self.check_good_repo()


class Test_Check(SimpleCommand):
    command_args = ["check"]

    @state.do_nothing
    def test_NoGit(self):
        self.check_error(versionflow.NoRepo)

    @state.make_git
    def test_JustGit(self):
        self.check_error(versionflow.NoGitFlow)

    @state.dirty_empty_git
    def test_DirtyEmptyGit(self):
        self.check_error(versionflow.DirtyRepo)

    @state.dirty_git
    def test_DirtyGit(self):
        self.check_error(versionflow.DirtyRepo)

    @state.clean_git
    def test_CleanGit(self):
        self.check_error(versionflow.NoGitFlow)

    @state.empty_gitflow
    def test_EmptyGitflow(self):
        self.check_error(versionflow.NoBumpVersion)

    @state.dirty_empty_gitflow
    def test_DirtyEmptyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

    @state.dirty_gitflow
    def test_DirtyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

    @state.clean_gitflow
    def test_CleanGitflow(self):
        self.check_error(versionflow.NoBumpVersion)

    @state.just_bump
    def test_JustBump(self):
        self.check_error(
            versionflow.NoRepo)

    @state.git_with_untracked_bump
    def test_EmptyGitAndBump(self):
        self.check_error(versionflow.NoGitFlow)

    @state.git_with_dirty_bump
    def test_GitAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

    @state.git_with_bump
    def test_GitAndBump(self):
        self.check_error(versionflow.NoGitFlow)

    @state.gitflow_with_untracked_bump
    def test_EmptyGitFlowAndBump(self):
        self.check_error(versionflow.BumpNotInGit)

    @state.gitflow_with_dirty_bump
    def test_GitFlowAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

    @state.gitflow_with_bump
    def test_GitFlowAndBump(self):
        self.check_error(versionflow.NoVersionTags)

    @state.empty_bad_tag_and_bump
    def test_EmptyBadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

    @state.bad_tag_and_bump
    def test_BadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

    @state.good_base_repo
    def test_GoodRepo(self):
        self.check_good_repo()


if __name__ == "__main__":
    unittest.main()
