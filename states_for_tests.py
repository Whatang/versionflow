from action_decorator import ActionDecorator, mktempdir
import gitflow.core
import git


@ActionDecorator
def _do_nothing(ctx):
    pass


@ActionDecorator
def _make_git(ctx):
    ctx.repo = git.Repo.init()


@_make_git.after
def _close_git(ctx):
    ctx.repo.close()


@ActionDecorator
def _do_initial_commit(ctx):
    assert not ctx.repo.is_dirty()
    with open("initial_file", "w") as handle:
        print >> handle, "initial"
    ctx.repo.index.add(["initial_file"])
    ctx.repo.index.commit("Initial commit")


@ActionDecorator
def _init_gitflow(ctx):
    ctx.gf_wrapper = gitflow.core.GitFlow()
    ctx.gf_wrapper.init()


@_init_gitflow.after
def _close_gitflow(ctx):
    ctx.gf_wrapper.repo.close()


@ActionDecorator
def _make_dirty(ctx):
    # Make a dirty repo
    with open("dirty", "w") as handle:
        print >> handle, "dirty"
    ctx.repo.index.add(["dirty"])


GOOD_VERSION = "1.0.2"
BAD_VERSION = "0.0.2"


@ActionDecorator
def _write_bumpversion(ctx):
    # Add bumpversion config
    if not hasattr(ctx, "setup_cfg"):
        ctx.setup_cfg = "setup.cfg"
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

# ActionDecorators can be combined
#
#       c = action1 | action2
#
# results in a new action c. When c is invoked it does action1
# then action2.


do_nothing = mktempdir | _do_nothing
make_git = mktempdir | _make_git

dirty_empty_git = make_git | _make_dirty
clean_git = make_git | _do_initial_commit
dirty_git = clean_git | _make_dirty

empty_gitflow = make_git | _init_gitflow
dirty_empty_gitflow = empty_gitflow | _make_dirty
clean_gitflow = empty_gitflow | _do_initial_commit
dirty_gitflow = clean_gitflow | _make_dirty

just_bump = mktempdir | _write_bumpversion

git_with_untracked_bump = make_git | _write_bumpversion
git_with_dirty_bump = git_with_untracked_bump | _stage_bumpversion
git_with_bump = git_with_dirty_bump | _commit_bumpversion

gitflow_with_untracked_bump = empty_gitflow | _write_bumpversion
gitflow_with_dirty_bump = gitflow_with_untracked_bump | _stage_bumpversion
gitflow_with_bump = gitflow_with_dirty_bump | _commit_bumpversion


_add_bumpversion = (_write_bumpversion |
                    _stage_bumpversion | _commit_bumpversion)

empty_bad_tag_and_bump = empty_gitflow | _add_bumpversion | _set_bad_tag
bad_tag_and_bump = clean_gitflow | _add_bumpversion | _set_bad_tag

good_base_repo = gitflow_with_bump | _set_good_tag
