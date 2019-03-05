import unittest

import click
import click.testing
import git
import gitflow.core

import versionflow
from action_decorator import ActionDecorator, mktempdir


@ActionDecorator
def do_nothing(ctx):
    pass


@ActionDecorator
def make_git(ctx):
    ctx.repo = git.Repo.init()


@make_git.after
def close_git(ctx):
    ctx.repo.close()


@ActionDecorator
def do_initial_commit(ctx):
    assert not ctx.repo.is_dirty()
    with open("initial_file", "w") as handle:
        print >> handle, "initial"
    ctx.repo.index.add(["initial_file"])
    ctx.repo.index.commit("Initial commit")


@ActionDecorator
def init_gitflow(ctx):
    ctx.gf_wrapper = gitflow.core.GitFlow()
    ctx.gf_wrapper.init()


@init_gitflow.after
def close_gitflow(ctx):
    ctx.gf_wrapper.repo.close()


@ActionDecorator
def make_dirty(ctx):
    # Make a dirty repo
    with open("dirty", "w") as handle:
        print >> handle, "dirty"
    ctx.repo.index.add(["dirty"])


GOOD_VERSION = "1.0.2"
BAD_VERSION = "0.0.2"


@ActionDecorator
def write_bumpversion(ctx):
    # Add bumpversion config
    if not hasattr(ctx, "setup_cfg"):
        ctx.setup_cfg = "setup.cfg"
    with open(ctx.setup_cfg, "w") as handle:
        print >> handle, "[bumpversion]"
        print >> handle, "current_version=" + GOOD_VERSION


@ActionDecorator
def stage_bumpversion(ctx):
    assert not ctx.repo.is_dirty()
    ctx.repo.index.add([ctx.setup_cfg])


@ActionDecorator
def commit_bumpversion(ctx):
    ctx.repo.index.commit("Add bumpversion info")


@ActionDecorator
def set_bad_tag(ctx):
    # Add non-matching tag
    ctx.repo.create_tag(BAD_VERSION, ref=ctx.repo.active_branch)


@ActionDecorator
def set_good_tag(ctx):
    # Add matching version tag
    ctx.repo.create_tag(GOOD_VERSION, ref=ctx.repo.active_branch)

# ActionDecorators can be combined
#
#       c = action1 | action2
#
# results in a new action c. When c is invoked it does action1
# then action2.


do_nothing = mktempdir | do_nothing
make_git = mktempdir | make_git

dirty_empty_git = make_git | make_dirty
clean_git = make_git | do_initial_commit
dirty_git = clean_git | make_dirty

empty_gitflow = make_git | init_gitflow
dirty_empty_gitflow = empty_gitflow | make_dirty
clean_gitflow = empty_gitflow | do_initial_commit
dirty_gitflow = clean_gitflow | make_dirty

just_bump = mktempdir | write_bumpversion

git_with_untracked_bump = make_git | write_bumpversion
git_with_dirty_bump = git_with_untracked_bump | stage_bumpversion
git_with_bump = git_with_dirty_bump | commit_bumpversion

gitflow_with_untracked_bump = empty_gitflow | write_bumpversion
gitflow_with_dirty_bump = gitflow_with_untracked_bump | stage_bumpversion
gitflow_with_bump = gitflow_with_dirty_bump | commit_bumpversion


add_bumpversion = write_bumpversion | stage_bumpversion | commit_bumpversion

empty_bad_tag_and_bump = empty_gitflow | add_bumpversion | set_bad_tag
bad_tag_and_bump = clean_gitflow | add_bumpversion | set_bad_tag

good_base_repo = gitflow_with_bump | set_good_tag


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

#     @do_nothing
#     def test_InitNoGit(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.0")

#     @make_git
#     def test_InitJustGit(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          "0.0.0")

    @dirty_empty_git
    def test_InitDirtyEmptyGit(self):
        self.check_error(versionflow.DirtyRepo)

    @dirty_git
    def test_InitDirtyGit(self):
        self.check_error(versionflow.DirtyRepo)

#     @clean_git
#     def test_InitCleanGit(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.0")

#     @empty_gitflow
#     def test_InitEmptyGitflow(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          "0.0.0")

    @dirty_empty_gitflow
    def test_InitDirtyEmptyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

    @dirty_gitflow
    def test_InitDirtyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

#     @clean_gitflow
#     def test_InitCleanGitflow(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.0")

#     @just_bump
#     def test_InitJustBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          TestDataMaker.GOOD_VERSION)

#     @git_with_untracked_bump
#     def test_InitEmptyGitAndBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(
#             vf_repo.bv_wrapper.current_version,
#             TestDataMaker.GOOD_VERSION)

    @git_with_dirty_bump
    def test_InitGitAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

#     @git_with_bump
#     def test_InitGitAndBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          TestDataMaker.GOOD_VERSION)

#     @gitflow_with_untracked_bump
#     def test_InitEmptyGitFlowAndBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          TestDataMaker.GOOD_VERSION)

    @gitflow_with_dirty_bump
    def test_InitGitFlowAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

#     @gitflow_with_bump
#     def test_InitGitFlowAndBump(self):
#         vf_repo = self.handler.process()
#         self.assertEqual(vf_repo.bv_wrapper.current_version,
#                          TestDataMaker.GOOD_VERSION)

    @empty_bad_tag_and_bump
    def test_InitEmptyBadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

    @bad_tag_and_bump
    def test_InitBadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

#     @good_base_repo
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

    @do_nothing
    def test_NoGit(self):
        self.check_error(versionflow.NoRepo)

    @make_git
    def test_JustGit(self):
        self.check_error(versionflow.NoGitFlow)

    @dirty_empty_git
    def test_DirtyEmptyGit(self):
        self.check_error(versionflow.DirtyRepo)

    @dirty_git
    def test_DirtyGit(self):
        self.check_error(versionflow.DirtyRepo)

    @clean_git
    def test_CleanGit(self):
        self.check_error(versionflow.NoGitFlow)

    @empty_gitflow
    def test_EmptyGitflow(self):
        self.check_error(versionflow.NoBumpVersion)

    @dirty_empty_gitflow
    def test_DirtyEmptyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

    @dirty_gitflow
    def test_DirtyGitflow(self):
        self.check_error(versionflow.DirtyRepo)

    @clean_gitflow
    def test_CleanGitflow(self):
        self.check_error(versionflow.NoBumpVersion)

    @just_bump
    def test_JustBump(self):
        self.check_error(
            versionflow.NoRepo)

    @git_with_untracked_bump
    def test_EmptyGitAndBump(self):
        self.check_error(versionflow.NoGitFlow)

    @git_with_dirty_bump
    def test_GitAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

    @git_with_bump
    def test_GitAndBump(self):
        self.check_error(versionflow.NoGitFlow)

    @gitflow_with_untracked_bump
    def test_EmptyGitFlowAndBump(self):
        self.check_error(versionflow.BumpNotInGit)

    @gitflow_with_dirty_bump
    def test_GitFlowAndDirtyBump(self):
        self.check_error(versionflow.DirtyRepo)

    @gitflow_with_bump
    def test_GitFlowAndBump(self):
        self.check_error(versionflow.NoVersionTags)

    @empty_bad_tag_and_bump
    def test_EmptyBadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

    @bad_tag_and_bump
    def test_BadTagAndBump(self):
        self.check_error(versionflow.BadVersionTags)

    @good_base_repo
    def test_GoodRepo(self):
        result = self.process()
        self.assertEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
