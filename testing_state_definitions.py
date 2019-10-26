from __future__ import print_function
import gitflow.core
import git
from action_decorator import ActionDecorator
import versionflow

INITIAL_FILE = u"initial_file"
DIRTY_FILE = u"dirty"
GOOD_VERSION = u"1.0.2"
NEXT_PATCH = u"1.0.3"
NEXT_MINOR = u"1.1.0"
NEXT_MAJOR = u"2.0.0"
BAD_VERSION = u"0.0.2"


@ActionDecorator
def _do_nothing(unused_ctx):
    pass


@ActionDecorator
def _make_git(ctx):
    ctx.repo = git.Repo.init()


@_make_git.after
def _close_git(ctx):
    if hasattr(ctx, "repo"):
        ctx.repo.close()
        del ctx.repo


@ActionDecorator
def _do_initial_commit(ctx):
    assert not ctx.repo.is_dirty()
    with open(INITIAL_FILE, "w") as handle:
        print("initial", file=handle)
    ctx.repo.index.add([INITIAL_FILE])
    ctx.repo.index.commit("Initial commit")


@ActionDecorator
def _init_gitflow(ctx):
    ctx.gf_wrapper = gitflow.core.GitFlow()
    ctx.gf_wrapper.init()


@_init_gitflow.after
def _close_gitflow(ctx):
    if hasattr(ctx, "gf_wrapper"):
        ctx.gf_wrapper.repo.close()
        del ctx.gf_wrapper


@ActionDecorator
def _make_dirty(ctx):
    # Make a dirty repo
    with open(DIRTY_FILE, "w") as handle:
        print(DIRTY_FILE, file=handle)
    ctx.repo.index.add([DIRTY_FILE])


@ActionDecorator
def _set_custom_bumpversion_config(ctx):
    # Use a non-standard BV config
    assert not hasattr(ctx, "setup_cfg")
    ctx.setup_cfg = "unusual_config"


@ActionDecorator
def _set_standard_bumpversion_config(ctx):
    # Use a non-standard BV config
    assert not hasattr(ctx, "setup_cfg")
    ctx.setup_cfg = versionflow.DEFAULT_BV_FILE


@ActionDecorator
def _write_bumpversion(ctx):
    # Add bumpversion config
    assert hasattr(ctx, "setup_cfg")
    with open(ctx.setup_cfg, "w") as handle:
        print("[bumpversion]", file=handle)
        print("current_version=" + GOOD_VERSION, file=handle)


@ActionDecorator
def _stage_bumpversion(ctx):
    assert not ctx.repo.is_dirty()
    ctx.repo.index.add([ctx.setup_cfg])


@ActionDecorator
def _commit_bumpversion(ctx):
    ctx.repo.index.commit("Add bumpversion info")


@ActionDecorator
def _merge_dev(ctx):
    repo = ctx.repo
    old_branch = repo.active_branch
    repo.heads.master.checkout()
    repo.git.merge("--commit", "--no-ff", "-m", "'Merge dev into master'", "develop")
    old_branch.checkout()


@ActionDecorator
def _merge_master(ctx):
    repo = ctx.repo
    old_branch = repo.active_branch
    repo.heads.develop.checkout()
    repo.git.merge("--commit", "--no-ff", "-m", "'Merge master into dev'", "master")
    old_branch.checkout()


@ActionDecorator
def _set_bad_tag(ctx):
    # Add non-matching tag
    ctx.repo.create_tag(BAD_VERSION, ref=ctx.repo.active_branch)


@ActionDecorator
def _set_good_tag(ctx):
    # Add matching version tag
    ctx.repo.create_tag(GOOD_VERSION, ref=ctx.repo.active_branch)


@ActionDecorator
def _ff_master(ctx):
    ctx.repo.heads.master.set_commit("HEAD").commit = ctx.repo.heads.develop.commit


@ActionDecorator
def _set_master_branch(ctx):
    ctx.repo.heads.master.checkout()


@ActionDecorator
def _set_develop_branch(ctx):
    ctx.repo.heads.develop.checkout()


@ActionDecorator
def _make_release_branch(ctx):
    ctx.release_name = "release/test"
    ctx.repo.create_head(ctx.release_name)


@ActionDecorator
def _set_release_branch(ctx):
    ctx.repo.heads[ctx.release_name].checkout()


@ActionDecorator
def _make_feature_branch(ctx):
    ctx.feature_name = "feature/test"
    ctx.repo.create_head(ctx.feature_name)


@ActionDecorator
def _set_feature_branch(ctx):
    ctx.repo.heads[ctx.feature_name].checkout()


# ActionDecorators can be combined
#
#       c = action1 | action2
#
# results in a new action c. When c is invoked it does action1
# then action2.
#
# Action decorators can be named
#
#       c= "name" * (a | b)
# results in a new action c which is the composition of a then b,
# and with c.__name__ = "name"

# pylint:disable=invalid-name

do_nothing = "nothing" * (_do_nothing)
make_git = "make_git" * (_make_git)
nothing_and_custom = "just_custom_set" * (_set_custom_bumpversion_config)

dirty_empty_git = "dirty_empty_git" * (make_git | _make_dirty)
clean_git = "clean_git" * (make_git | _do_initial_commit)
dirty_git = "dirty_git" * (clean_git | _make_dirty)

empty_gitflow = "empty_gitflow" * (make_git | _init_gitflow)
dirty_empty_gitflow = "dirty_empty_gitflow" * (empty_gitflow | _make_dirty)
clean_gitflow = "clean_gitflow" * (empty_gitflow | _do_initial_commit)
dirty_gitflow = "dirty_gitflow" * (clean_gitflow | _make_dirty)

just_bump = "just_bump" * (_set_standard_bumpversion_config | _write_bumpversion)

git_with_untracked_bump = "git_with_untracked_bump" * (
    make_git | _set_standard_bumpversion_config | _write_bumpversion
)
git_with_dirty_bump = "git_with_dirty_bump" * (
    git_with_untracked_bump | _stage_bumpversion
)
git_with_bump = "git_with_bump" * (git_with_dirty_bump | _commit_bumpversion)

gitflow_with_untracked_bump = "gitflow_with_untracked_bump" * (
    clean_gitflow | _set_standard_bumpversion_config | _write_bumpversion
)
gitflow_with_dirty_bump = "gitflow_with_dirty_bump" * (
    gitflow_with_untracked_bump | _stage_bumpversion
)
gitflow_with_bump = "gitflow_with_bump" * (
    gitflow_with_dirty_bump | _commit_bumpversion
)

_add_bumpversion = _write_bumpversion | _stage_bumpversion | _commit_bumpversion

_set_merged_tag = (
    _merge_dev
    | _set_master_branch
    | _set_good_tag
    | _set_develop_branch
    | _merge_master
)
_set_merged_bad_tag = (
    _merge_dev | _set_master_branch | _set_bad_tag | _set_develop_branch | _merge_master
)

empty_bad_tag_and_bump = "empty_bad_tag_and_bump" * (
    empty_gitflow
    | _set_standard_bumpversion_config
    | _add_bumpversion
    | _set_merged_bad_tag
)
bad_tag_and_bump = "bad_tag_and_bump" * (
    clean_gitflow
    | _set_standard_bumpversion_config
    | _add_bumpversion
    | _set_merged_bad_tag
)


good_dev_branch = "good_dev_branch" * (gitflow_with_bump | _set_merged_tag)

good_base_repo = "good_base_repo" * (good_dev_branch | _ff_master)

good_custom_config = "custom_bump" * (
    clean_gitflow
    | _set_custom_bumpversion_config
    | _add_bumpversion
    | _merge_dev
    | _set_master_branch
    | _set_good_tag
    | _set_develop_branch
    | _merge_master
)

version_tag_on_wrong_branch = "version_tag_on_wrong_branch" * (
    clean_gitflow | _set_custom_bumpversion_config | _add_bumpversion | _set_good_tag
)

on_bad_master = "on_bad_master" * (
    gitflow_with_bump | _set_good_tag | _set_master_branch
)
on_master = "on_master" * (good_base_repo | _set_master_branch)
existing_release = "existing_release" * (good_base_repo | _make_release_branch)
on_release_branch = "on_release_branch" * (existing_release | _set_release_branch)
with_feature = "with_feature" * (good_base_repo | _make_feature_branch)
on_feature = "on_feature" * (with_feature | _set_feature_branch)
