from action_decorator import ActionDecorator, mktempdir
import gitflow.core
import git

INITIAL_FILE = "initial_file"
DIRTY_FILE = "dirty"
GOOD_VERSION = "1.0.2"
NEXT_PATCH = "1.0.3"
NEXT_MINOR = "1.1.0"
NEXT_MAJOR = "2.0.0"
BAD_VERSION = "0.0.2"
BV_CONFIG = "setup.cfg"


@ActionDecorator
def _do_nothing(ctx):
    pass


@ActionDecorator
def _make_git(ctx):
    ctx.repo = git.Repo.init()


@_make_git.after
def _close_git(ctx):
    ctx.repo.git.clear_cache()
    ctx.repo.close()
    del ctx.repo.git
    del ctx.repo


@ActionDecorator
def _do_initial_commit(ctx):
    assert not ctx.repo.is_dirty()
    with open(INITIAL_FILE, "w") as handle:
        print >> handle, "initial"
    ctx.repo.index.add([INITIAL_FILE])
    ctx.repo.index.commit("Initial commit")


@ActionDecorator
def _init_gitflow(ctx):
    ctx.gf_wrapper = gitflow.core.GitFlow()
    ctx.gf_wrapper.init()


@_init_gitflow.after
def _close_gitflow(ctx):
    ctx.gf_wrapper.repo.git.clear_cache()
    ctx.gf_wrapper.git.clear_cache()
    ctx.gf_wrapper.repo.close()
    del ctx.gf_wrapper.repo.git
    del ctx.gf_wrapper.repo
    del ctx.gf_wrapper


@ActionDecorator
def _make_dirty(ctx):
    # Make a dirty repo
    with open(DIRTY_FILE, "w") as handle:
        print >> handle, DIRTY_FILE
    ctx.repo.index.add([DIRTY_FILE])


@ActionDecorator
def _write_bumpversion(ctx):
    # Add bumpversion config
    if not hasattr(ctx, "setup_cfg"):
        ctx.setup_cfg = BV_CONFIG
    with open(ctx.setup_cfg, "w") as handle:
        print >> handle, "[bumpversion]"
        print >> handle, "current_version=" + GOOD_VERSION


@ActionDecorator
def _stage_bumpversion(ctx):
    assert not ctx.repo.is_dirty()
    ctx.repo.index.add([ctx.setup_cfg])


@ActionDecorator
def _commit_bumpversion(ctx):
    ctx.repo.index.commit("Add bumpversion info")


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
    ctx.repo.heads.master.set_commit(
        'HEAD').commit = ctx.repo.heads.develop.commit


@ActionDecorator
def _set_master_branch(ctx):
    ctx.repo.heads.master.checkout()


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


do_nothing = "nothing" * (mktempdir | _do_nothing)
make_git = "make_git" * (mktempdir | _make_git)

dirty_empty_git = "dirty_empty_git" * (make_git | _make_dirty)
clean_git = "clean_git" * (make_git | _do_initial_commit)
dirty_git = "dirty_git" * (clean_git | _make_dirty)

empty_gitflow = "empty_gitflow" * (make_git | _init_gitflow)
dirty_empty_gitflow = "dirty_empty_gitflow" * (empty_gitflow | _make_dirty)
clean_gitflow = "clean_gitflow" * (empty_gitflow | _do_initial_commit)
dirty_gitflow = "dirty_gitflow" * (clean_gitflow | _make_dirty)

just_bump = "just_bump" * (mktempdir | _write_bumpversion)

git_with_untracked_bump = (
    "git_with_untracked_bump" * (make_git | _write_bumpversion))
git_with_dirty_bump = ("git_with_dirty_bump" *
                       (git_with_untracked_bump | _stage_bumpversion))
git_with_bump = "git_with_bump" * (git_with_dirty_bump | _commit_bumpversion)

gitflow_with_untracked_bump = (
    "gitflow_with_untracked_bump" * (empty_gitflow | _write_bumpversion))
gitflow_with_dirty_bump = ("gitflow_with_dirty_bump" *
                           (gitflow_with_untracked_bump | _stage_bumpversion))
gitflow_with_bump = ("gitflow_with_bump" *
                     (gitflow_with_dirty_bump | _commit_bumpversion))


_add_bumpversion = (_write_bumpversion |
                    _stage_bumpversion | _commit_bumpversion)

empty_bad_tag_and_bump = ("empty_bad_tag_and_bump" *
                          (empty_gitflow | _add_bumpversion | _set_bad_tag))
bad_tag_and_bump = ("bad_tag_and_bump" *
                    (clean_gitflow | _add_bumpversion | _set_bad_tag))


good_dev_branch = ("good_dev_branch" *
                   (gitflow_with_bump | _set_good_tag))

good_base_repo = ("good_base_repo" *
                  (good_dev_branch | _ff_master))


on_bad_master = "on_bad_master" * \
    (good_dev_branch | _set_master_branch)
on_master = "on_master" * (good_base_repo | _set_master_branch)
existing_release = "existing_release" * (good_base_repo | _make_release_branch)
on_release_branch = ("on_release_branch" *
                     (existing_release | _set_release_branch))
with_feature = "with_feature" * (good_base_repo | _make_feature_branch)
on_feature = "on_feature" * (with_feature | _set_feature_branch)
