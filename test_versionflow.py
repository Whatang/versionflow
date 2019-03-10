import versionflow
import states_for_tests as state
import contextlib
import cProfile
import os
import unittest
import traceback
import functools

import attr
import click
import click.testing
import git.cmd
import git


def with_breakpoint(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


git.cmd.Git.clear_cache = with_breakpoint(git.cmd.Git.clear_cache)


@contextlib.contextmanager
def profile():
    cp = cProfile.Profile()
    cp.enable()
    try:
        yield
    finally:
        cp.disable()
        cp.print_stats("tottime")


@attr.s
class Result(object):
    def check(self, testclass, result):
        raise NotImplementedError()


@attr.s
class ErrorResult(Result):
    error = attr.ib()

    def check(self, testclass, result):
        try:
            testclass.assertIsInstance(result.exception, SystemExit)
            testclass.assertEqual(result.exit_code, 1)
            expected_error = self.error
            if issubclass(expected_error, versionflow.VersionFlowError):
                expected_error = expected_error()
            testclass.assert_(
                result.stdout.endswith(
                    str(expected_error) +
                    "\n" +
                    "Aborted!\n"))
        except AssertionError:
            print result.stdout
            if hasattr(result, "exc_info"):
                traceback.print_exception(*result.exc_info)
            raise


@attr.s
class Success(Result):
    version = attr.ib()

    def check(self, testclass, result):
        try:
            testclass.assertEqual(result.exit_code, 0)
            # It is a git repo.
            testclass.assert_(os.path.exists(".git"))
            with versionflow.git_context() as repo:
                # It is not dirty.
                testclass.assertFalse(repo.is_dirty())
                with versionflow.gitflow_context() as gf:
                    # It is a gitflow repo.
                    testclass.assert_(gf.is_initialized())
                    # Bumpversion version number present, in git
                    # repo, and matches git tag
                    testclass.assert_(os.path.exists(state.BV_CONFIG))
                    testclass.assert_(
                        repo.active_branch.commit.tree / state.BV_CONFIG)
                    bv = versionflow.BumpVersionWrapper.from_existing(
                        state.BV_CONFIG)
                    # - The version number is what we expect it to be.
                    testclass.assertEqual(bv.current_version, self.version)
                    # TODO: The output is what we expect.
        except BaseException:
            print(result.stdout)
            if hasattr(result, "exc_info"):
                traceback.print_exception(*result.exc_info)
            raise


@attr.s
class StateTest(object):
    state = attr.ib()
    expected = attr.ib()
    name = attr.ib()

    @classmethod
    def _make(cls, state, version=None, error_class=None, name=None):
        if error_class is None:
            if version is None:
                version = state.GOOD_VERSION
            expected = Success(version)
        else:
            if error_class is None:
                raise TypeError("error class cannot be None")
            expected = ErrorResult(error=error_class)
        return cls(state, expected, name)

    @classmethod
    def good(cls, state, version, name=None):
        return cls._make(state, version=version, name=name)

    @classmethod
    def bad(cls, state, error_class, name=None):
        return cls._make(state, error_class=error_class, name=name)

    def _make_test_method(self, test_class, prefix):
        name = self.name
        if name is None:
            name = self.state.__name__
        name = "test_" + prefix + "_" + name
        @self.state
        def test_method(slf):
            result = slf.process()
            self.expected.check(slf, result)
        return name, test_method

    @classmethod
    def make_tests(cls, testcase):
        if not hasattr(testcase, "state_tests"):
            return testcase
        prefix = testcase.__name__
        if prefix.startswith("Test"):
            prefix = prefix[4:]
        prefix = prefix.lstrip("_")
        for test in testcase.state_tests:
            name, func = cls._make_test_method(test, testcase, prefix)
            func.__name__ = name
            setattr(testcase, name, func)
        return testcase


bad = StateTest.bad


def start(s): return StateTest.good(s, versionflow.START_VERSION)


def good(s): return StateTest.good(s, state.GOOD_VERSION)


def patch(s): return StateTest.good(s, state.NEXT_PATCH)


def minor(s): return StateTest.good(s, state.NEXT_MINOR)


def major(s): return StateTest.good(s, state.NEXT_MAJOR)


class BaseTest(unittest.TestCase):
    command_args = []

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def process(self, *args):
        return self.runner.invoke(
            versionflow.cli,
            self.command_args)


_always_bad_states = [bad(state.dirty_empty_git, versionflow.DirtyRepo),
                      bad(state.dirty_git, versionflow.DirtyRepo),
                      bad(state.dirty_empty_gitflow, versionflow.DirtyRepo),
                      bad(state.dirty_gitflow, versionflow.DirtyRepo),
                      bad(state.git_with_dirty_bump, versionflow.DirtyRepo),
                      bad(state.gitflow_with_dirty_bump, versionflow.DirtyRepo),
                      bad(state.empty_bad_tag_and_bump, versionflow.BadVersionTags),
                      bad(state.bad_tag_and_bump, versionflow.BadVersionTags),

                      ]


@StateTest.make_tests
class Test_Init(BaseTest):
    command_args = ["init"]
    state_tests = (_always_bad_states + [
        start(state.do_nothing),
        start(state.make_git),
        start(state.clean_git),
        start(state.empty_gitflow),
        start(state.clean_gitflow),
        good(state.just_bump),
        good(state.git_with_untracked_bump),
        good(state.git_with_bump),
        good(state.gitflow_with_untracked_bump),
        good(state.gitflow_with_bump),
        good(state.good_dev_branch),
        good(state.on_bad_master),
        good(state.good_base_repo),
        good(state.on_master),
        good(state.existing_release),
        good(state.on_release_branch),
        good(state.with_feature),
        good(state.on_feature)
    ])


@StateTest.make_tests
class Test_Check(BaseTest):
    command_args = ["check"]
    state_tests = (_always_bad_states + [
        bad(state.do_nothing, versionflow.NoRepo),
        bad(state.make_git, versionflow.NoGitFlow),
        bad(state.clean_git, versionflow.NoGitFlow),
        bad(state.empty_gitflow, versionflow.NoBumpVersion),
        bad(state.clean_gitflow, versionflow.NoBumpVersion),
        bad(state.just_bump, versionflow.NoRepo),
        bad(state.git_with_untracked_bump, versionflow.NoGitFlow),
        bad(state.git_with_bump, versionflow.NoGitFlow),
        bad(state.gitflow_with_untracked_bump, versionflow.BumpNotInGit),
        bad(state.gitflow_with_bump, versionflow.NoVersionTags),
        bad(state.on_bad_master, versionflow.NoBumpVersion),
        good(state.good_dev_branch),
        good(state.good_base_repo),
        good(state.on_master),
        good(state.existing_release),
        good(state.on_release_branch),
        good(state.with_feature),
        good(state.on_feature)
    ])


def make_bump_tests(bump):
    return (_always_bad_states +
            [
                bad(state.on_bad_master, versionflow.NoBumpVersion),
                bad(state.existing_release, versionflow.AlreadyReleasing),
                bad(state.on_release_branch, versionflow.AlreadyReleasing),
                bump(state.good_base_repo),
                bump(state.on_master),
                bump(state.with_feature),
                bump(state.on_feature)
            ])


@StateTest.make_tests
class Test_Patch(BaseTest):
    command_args = ["patch"]
    state_tests = make_bump_tests(patch)


@StateTest.make_tests
class Test_Minor(BaseTest):
    command_args = ["minor"]
    state_tests = make_bump_tests(minor)


@StateTest.make_tests
class Test_Major(BaseTest):
    command_args = ["major"]
    state_tests = make_bump_tests(minor)


if __name__ == "__main__":
    unittest.main()
