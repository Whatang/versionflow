from __future__ import print_function
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

import versionflow
import testing_state_definitions as test_states
import action_decorator


@contextlib.contextmanager
def profile():
    cprof = cProfile.Profile()
    cprof.enable()
    try:
        yield
    finally:
        cprof.disable()
        cprof.print_stats("tottime")


@attr.s
class Result(object):
    def check(self, testclass, result, ctx):
        raise NotImplementedError()


@attr.s
class ErrorResult(Result):
    error = attr.ib()

    def check(self, testclass, result, ctx):
        testclass.assertIsInstance(result.exception, SystemExit)
        testclass.assertEqual(result.exit_code, 1)
        expected_error = self.error
        if issubclass(expected_error, versionflow.VersionFlowError):
            expected_error = expected_error()
        testclass.assertTrue(
            result.stdout.endswith(str(expected_error) + "\n" + "Aborted!\n")
        )


@attr.s
class Success(Result):
    version = attr.ib()

    def check(self, testclass, result, ctx):
        testclass.assertEqual(result.exit_code, 0)
        # It is a git repo.
        testclass.assertTrue(os.path.exists(".git"))
        with versionflow.git_context() as repo:
            # It is not dirty.
            testclass.assertFalse(repo.is_dirty())
            with versionflow.gitflow_context() as gflow:
                # It is a gitflow repo.
                testclass.assertTrue(gflow.is_initialized())
                setup_cfg = getattr(
                    ctx, "setup_cfg", versionflow.DEFAULT_BV_FILE)
            # Bumpversion version number present in git repo
            # on develop branch
            repo.heads.develop.checkout()
            testclass.assertTrue(os.path.exists(setup_cfg))
            testclass.assertTrue(repo.active_branch.commit.tree / setup_cfg)
        bumpver = versionflow.BumpVersionWrapper.from_existing(setup_cfg)
        # - The version number is what we expect it to be.
        testclass.assertEqual(bumpver.current_version, self.version)
        # Check that the git version tag is present and is what we
        # expect
        tag_version = versionflow.Config.get_last_version()
        testclass.assertEqual(tag_version, self.version)
        # TODO: The output is what we expect.
        # Check that we are left with a consistent repo
        if setup_cfg == versionflow.DEFAULT_BV_FILE:
            testclass.runner.invoke(versionflow.cli, args=["check"])
        else:
            testclass.runner.invoke(
                versionflow.cli, args=["--config", setup_cfg, "check"]
            )


@attr.s
class StateTest(object):
    state = attr.ib()
    expected = attr.ib()
    name = attr.ib()

    @classmethod
    def _make(cls, state, version=None, error_class=None, name=None):
        if error_class is None:
            if version is None:
                version = test_states.GOOD_VERSION
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

    def _make_test_method(self, unused_test_class, prefix):
        name = self.name
        if name is None:
            name = self.state.__name__
        name = "test_" + prefix + "_" + name

        @self.state("context")
        def test_method(slf, context):
            if (
                hasattr(context, "setup_cfg")
                and context.setup_cfg != versionflow.DEFAULT_BV_FILE
            ):
                slf.command_args = ["--config",
                                    context.setup_cfg] + slf.command_args
            result = slf.process()
            click.echo(result.stdout)
            return result, context

        @action_decorator.mktempdir
        def overall_test(slf):
            result, context = test_method(slf)
            try:
                self.expected.check(slf, result, context)
            except AssertionError as exc:
                if hasattr(result, "exc_info"):
                    traceback.print_exception(*result.exc_info)
                raise

        return name, overall_test

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


def start(state):
    return StateTest.good(state, versionflow.START_VERSION)


def good(state):
    return StateTest.good(state, test_states.GOOD_VERSION)


def patch(state):
    return StateTest.good(state, test_states.NEXT_PATCH)


def minor(state):
    return StateTest.good(state, test_states.NEXT_MINOR)


def major(state):
    return StateTest.good(state, test_states.NEXT_MAJOR)


class BaseTest(unittest.TestCase):
    command_args = []

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def process(self, *unused_args):
        return self.runner.invoke(versionflow.cli, args=self.command_args)


_always_bad_states = [
    bad(test_states.dirty_empty_git, versionflow.DirtyRepo),
    bad(test_states.dirty_git, versionflow.DirtyRepo),
    bad(test_states.dirty_empty_gitflow, versionflow.DirtyRepo),
    bad(test_states.dirty_gitflow, versionflow.DirtyRepo),
    bad(test_states.git_with_dirty_bump, versionflow.DirtyRepo),
    bad(test_states.gitflow_with_dirty_bump, versionflow.DirtyRepo),
    bad(test_states.empty_bad_tag_and_bump, versionflow.BadVersionTags),
    bad(test_states.bad_tag_and_bump, versionflow.BadVersionTags),
    bad(test_states.version_tag_on_wrong_branch,
        versionflow.VersionTagOnWrongBranch),
]


@StateTest.make_tests
class Test_Init(BaseTest):
    command_args = ["init"]
    state_tests = _always_bad_states + [
        start(test_states.do_nothing),
        start(test_states.make_git),
        start(test_states.clean_git),
        start(test_states.empty_gitflow),
        start(test_states.clean_gitflow),
        start(test_states.nothing_and_custom),
        good(test_states.just_bump),
        good(test_states.git_with_untracked_bump),
        good(test_states.git_with_bump),
        good(test_states.gitflow_with_untracked_bump),
        good(test_states.gitflow_with_bump),
        good(test_states.good_dev_branch),
        good(test_states.on_bad_master),
        good(test_states.good_base_repo),
        good(test_states.on_master),
        good(test_states.existing_release),
        good(test_states.on_release_branch),
        good(test_states.with_feature),
        good(test_states.on_feature),
        good(test_states.good_custom_config),
    ]


@StateTest.make_tests
class Test_Check(BaseTest):
    command_args = ["check"]
    state_tests = _always_bad_states + [
        bad(test_states.do_nothing, versionflow.NoRepo),
        bad(test_states.make_git, versionflow.NoGitFlow),
        bad(test_states.clean_git, versionflow.NoGitFlow),
        bad(test_states.empty_gitflow, versionflow.NoBumpVersion),
        bad(test_states.clean_gitflow, versionflow.NoBumpVersion),
        bad(test_states.just_bump, versionflow.NoRepo),
        bad(test_states.git_with_untracked_bump, versionflow.NoGitFlow),
        bad(test_states.git_with_bump, versionflow.NoGitFlow),
        bad(test_states.gitflow_with_untracked_bump, versionflow.BumpNotInGit),
        bad(test_states.gitflow_with_bump, versionflow.NoVersionTags),
        bad(test_states.on_bad_master, versionflow.NoBumpVersion),
        bad(test_states.nothing_and_custom, versionflow.NoRepo),
        good(test_states.good_dev_branch),
        good(test_states.good_base_repo),
        good(test_states.on_master),
        good(test_states.existing_release),
        good(test_states.on_release_branch),
        good(test_states.with_feature),
        good(test_states.on_feature),
        good(test_states.good_custom_config),
    ]


def make_bump_tests(bump_command):
    return _always_bad_states + [
        bad(test_states.on_bad_master, versionflow.NoBumpVersion),
        bad(test_states.existing_release, versionflow.AlreadyReleasing),
        bad(test_states.on_release_branch, versionflow.AlreadyReleasing),
        bad(test_states.nothing_and_custom, versionflow.NoRepo),
        bump_command(test_states.good_base_repo),
        bump_command(test_states.on_master),
        bump_command(test_states.with_feature),
        bump_command(test_states.on_feature),
        bump_command(test_states.good_custom_config),
    ]


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
    state_tests = make_bump_tests(major)


if __name__ == "__main__":
    unittest.main()
