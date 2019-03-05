import unittest

import click
import click.testing

import versionflow

import states_for_tests as state


class Test_Init(unittest.TestCase):
    def setUp(self):
        self.runner = click.testing.CliRunner()

    def process(self):
        return self.runner.invoke(
            versionflow.cli,
            ["check"],
            catch_exceptions=False)

    def check_error(self, error_class):
        self.assertRaises(error_class, self.process)

# TODO: work out how to test for success in these cases

#     @state.do_nothing
#     def test_InitNoGit(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.0")

#     @state.make_git
#     def test_InitJustGit(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          "0.0.0")

    @state.dirty_empty_git
    def test_InitDirtyEmptyGit(self):
        self.check_error(versionflow.DirtyRepo)

    @state.dirty_git
    def test_InitDirtyGit(self):
        self.check_error(versionflow.DirtyRepo)

#     @state.clean_git
#     def test_InitCleanGit(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.0")

#     @state.empty_gitflow
#     def test_InitEmptyGitflow(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          "0.0.0")

    @state.dirty_empty_gitflow
    def test_InitDirtyEmptyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

    @state.dirty_gitflow
    def test_InitDirtyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

#     @state.clean_gitflow
#     def test_InitCleanGitflow(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.0")

#     @state.just_bump
#     def test_InitJustBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          TestDataMaker.GOOD_VERSION)

#     @state.git_with_untracked_bump
#     def test_InitEmptyGitAndBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(
#             vf_repo.bv_wrapper.current_version,
#             TestDataMaker.GOOD_VERSION)

    @state.git_with_dirty_bump
    def test_InitGitAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

#     @state.git_with_bump
#     def test_InitGitAndBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          TestDataMaker.GOOD_VERSION)

#     @state.gitflow_with_untracked_bump
#     def test_InitEmptyGitFlowAndBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          TestDataMaker.GOOD_VERSION)

    @state.gitflow_with_dirty_bump
    def test_InitGitFlowAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

#     @state.gitflow_with_bump
#     def test_InitGitFlowAndBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          TestDataMaker.GOOD_VERSION)

    @state.empty_bad_tag_and_bump
    def test_InitEmptyBadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

    @state.bad_tag_and_bump
    def test_InitBadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

#     @state.good_base_repo
#     def test_InitRepoAlreadyGood(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(
#             vf_repo.bv_wrapper.current_version,
#             TestDataMaker.GOOD_VERSION)


class Test_Check(unittest.TestCase):

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def process(self):
        return self.runner.invoke(
            versionflow.cli,
            ["check"],
            catch_exceptions=False)

    def check_error(self, error_class):
        self.assertRaises(error_class, self.process)

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
        result = self.process()
        self.assertEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
