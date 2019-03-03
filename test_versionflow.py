import unittest
import functools
import os
import click
import click.testing
import git
import gitflow.core
import attr
from versionflow import VersionFlowChecker, Config


def setup_with_context_manager(testcase, cm):
    """Use a contextmanager to setUp a test case."""
    val = cm.__enter__()
    testcase.addCleanup(cm.__exit__, None, None, None)
    return val


class TestVersion(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testFromBumpversion(self):
        pass


class TestBumpVersionWrapper(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testFromExisting(self):
        pass

    def testInitialise(self):
        pass


class Flag(object):
    next_flag = 1

    def __init__(self, name, flag_val=None):
        self.name = name
        if flag_val is None:
            flag_val = Flag.next_flag
            Flag.next_flag *= 2
        self.flag = flag_val

    def __call__(self, state):
        if self.flag == 0:
            return state.flag == 0
        answer = ((self.flag & state.flag) == self.flag)
        return answer

    def __or__(self, other):
        if other.flag == 0:
            return self
        if self.flag == 0:
            return other
        return Flag(self.name + "|" + other.name,
                    self.flag | other.flag)

    def __ror__(self, other):
        if other.flag == 0:
            return self
        if self.flag == 0:
            return other
        return Flag(other.name + "|" + self.name,
                    self.flag | other.flag)

    def __str__(self):
        return self.name


@attr.s
class TestDataMaker(object):
    state = attr.ib()

    _NOTHING = Flag("Nothing", 0)
    _IS_GIT = Flag("IsGitRepo")
    _HAS_INITIAL_COMMIT = Flag("InitialCommit") | _IS_GIT
    _IS_DIRTY = Flag("IsDirty") | _IS_GIT
    _IS_GITFLOW = Flag("GitFlow") | _IS_GIT
    _HAS_BUMP = Flag("Bump")
    _ADD_BUMP = Flag("BumpStaged") | _HAS_BUMP | _IS_GIT
    _COMMIT_BUMP = Flag("BumpCommitted") | _ADD_BUMP
    _HAS_BAD_TAG = Flag("BadTag") | _IS_GIT
    _HAS_GOOD_TAG = Flag("GoodTag") | _IS_GIT

    NOTHING = _NOTHING
    JUST_GIT = _IS_GIT
    DIRTY_EMPTY_GIT_REPO = _IS_DIRTY
    DIRTY_GIT_REPO = _HAS_INITIAL_COMMIT | _IS_DIRTY
    CLEAN_GIT_REPO = _HAS_INITIAL_COMMIT
    DIRTY_EMPTY_GITFLOW_REPO = _IS_GITFLOW | _IS_DIRTY
    DIRTY_GITFLOW_REPO = _IS_GITFLOW | _HAS_INITIAL_COMMIT | _IS_DIRTY
    CLEAN_EMPTY_GITFLOW = _IS_GITFLOW
    CLEAN_GITFLOW = _IS_GITFLOW | _HAS_INITIAL_COMMIT
    JUST_BUMP = _HAS_BUMP
    EMPTY_GIT_AND_BUMP = _IS_GIT | _HAS_BUMP
    GIT_AND_DIRTY_BUMP = _IS_GIT | _ADD_BUMP
    GIT_AND_BUMP = _HAS_INITIAL_COMMIT | _COMMIT_BUMP
    EMPTY_GITFLOW_AND_BUMP = _IS_GITFLOW | _HAS_BUMP
    GITFLOW_AND_DIRTY_BUMP = _IS_GITFLOW | _ADD_BUMP
    GITFLOW_AND_BUMP = _IS_GITFLOW | _HAS_INITIAL_COMMIT | _COMMIT_BUMP
    EMPTY_BAD_TAG_AND_BUMP = _HAS_BAD_TAG | _IS_GITFLOW | _COMMIT_BUMP
    BAD_TAG_AND_BUMP = (_HAS_BAD_TAG | _IS_GITFLOW |
                        _COMMIT_BUMP | _HAS_INITIAL_COMMIT)
    GOOD_REPO = (_HAS_GOOD_TAG | _IS_GITFLOW |
                 _COMMIT_BUMP | _HAS_INITIAL_COMMIT)

    GOOD_VERSION = "1.0.2"
    BAD_VERSION = "0.0.2"

    def __call__(self, func):
        def make_data():
            if self._IS_GIT(self.state):
                # Create git repo
                repo = git.Repo.init()
            if self._HAS_INITIAL_COMMIT(self.state):
                # Make an initial commit
                with open("initial_file", "w") as handle:
                    print >> handle, "initial"
                repo.index.add(["initial_file"])
                repo.index.commit("Initial commit")
            if self._IS_GITFLOW(self.state):
                # Initialize git flow
                gf_wrapper = gitflow.core.GitFlow()
                gf_wrapper.init()
            if self._IS_DIRTY(self.state):
                # Make a dirty repo
                with open("dirty", "w") as handle:
                    print >> handle, "dirty"
                repo.index.add(["dirty"])
            if self._HAS_BUMP(self.state):
                # Add bumpversion config
                with open("setup.cfg", "w") as handle:
                    print >> handle, "[bumpversion]"
                    print >> handle, "current_version=" + self.GOOD_VERSION
            if self._ADD_BUMP(self.state):
                repo.index.add(["setup.cfg"])
                if self._COMMIT_BUMP(self.state):
                    repo.index.commit("Add bumpversion info")
            if self._HAS_BAD_TAG(self.state):
                # Add non-matching tag
                repo.create_tag(self.BAD_VERSION, ref=repo.active_branch)
            if self._HAS_GOOD_TAG(self.state):
                if self._HAS_BAD_TAG(self.state):
                    # Remove non-matching tag
                    repo.delete_tag(self.BAD_VERSION)
                # Add matching version tag
                repo.create_tag(self.GOOD_VERSION, ref=repo.active_branch)

        state_name = self.get_state_name(self.state)
        @functools.wraps(func)
        def wrapper(slf, *args, **kwargs):
            make_data()
            slf.state_checker[self.state][0] = True
            if state_name is not None:
                slf.tests_run.add(state_name)
            return func(slf, *args, **kwargs)
        if state_name is not None:
            wrapper.tested_state = state_name
        return wrapper

    @classmethod
    def iter_states(cls):
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            cls_attr = getattr(cls, attr_name)
            if not isinstance(cls_attr, Flag):
                continue
            yield (attr_name, cls_attr)

    @classmethod
    def get_state_name(cls, state):
        for state_name, state_flag in cls.iter_states():
            if state_flag.flag == state.flag:
                return state_name
        return None

    @classmethod
    def state_checker(cls):
        states = {}
        for attr_name, cls_attr in cls.iter_states():
            states[cls_attr] = [False, attr_name]
        return states

    @classmethod
    def make_state_checker(cls, klass):
        if hasattr(klass, "setUpClass"):
            old_setup = klass.setUpClass
        else:
            def old_setup(): return None

        @functools.wraps(klass.setUpClass)
        def wrapper(kls):
            old_setup()
            kls.state_checker = cls.state_checker()
            kls.tests_run = set()
        klass.setUpClass = classmethod(wrapper)

        if hasattr(klass, "tearDownClass"):
            old_teardown = klass.tearDownClass
        else:
            def old_teardown(): return None

        @functools.wraps(klass.tearDownClass)
        def td_wrapper(kls):
            old_teardown()
            if len(kls.testDataWrapperMethods) == len(kls.tests_run):
                errors = []
                for [tested, state_name] in kls.state_checker.itervalues():
                    if not tested:
                        errors.append(state_name)
                assert errors == [], (", ".join(errors)) + " not tested"
        klass.tearDownClass = classmethod(td_wrapper)

        klass.testDataWrapperMethods = set()

        for attr_name in dir(klass):
            if not attr_name.startswith("test_"):
                continue
            test_method = getattr(klass, attr_name)
            if hasattr(test_method, "tested_state"):
                state_name = getattr(test_method, "tested_state")
                klass.testDataWrapperMethods.add(state_name)
        return klass


@TestDataMaker.make_state_checker
class TestVersionFlowChecker_Check(unittest.TestCase):

    def setUp(self):
        self.runner = click.testing.CliRunner()
        self.fs = setup_with_context_manager(
            self, self.runner.isolated_filesystem())
        self.handler = VersionFlowChecker.from_config(config=Config(
            os.getcwd(), bumpversion_config="setup.cfg"), create=False)

    @TestDataMaker(TestDataMaker.NOTHING)
    def test_NoGit(self):
        self.assertRaises(VersionFlowChecker.NoRepo, self.handler.process)

    @TestDataMaker(TestDataMaker.JUST_GIT)
    def test_JustGit(self):
        self.assertRaises(VersionFlowChecker.NoGitFlow, self.handler.process)

    @TestDataMaker(TestDataMaker.DIRTY_EMPTY_GIT_REPO)
    def test_DirtyEmptyGit(self):
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    @TestDataMaker(TestDataMaker.DIRTY_GIT_REPO)
    def test_DirtyGit(self):
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    @TestDataMaker(TestDataMaker.CLEAN_GIT_REPO)
    def test_CleanGit(self):
        self.assertRaises(VersionFlowChecker.NoGitFlow, self.handler.process)

    @TestDataMaker(TestDataMaker.CLEAN_EMPTY_GITFLOW)
    def test_EmptyGitflow(self):
        self.assertRaises(
            VersionFlowChecker.NoBumpVersion,
            self.handler.process)

    @TestDataMaker(TestDataMaker.DIRTY_EMPTY_GITFLOW_REPO)
    def test_DirtyEmptyGitflow(self):
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    @TestDataMaker(TestDataMaker.DIRTY_GITFLOW_REPO)
    def test_DirtyGitflow(self):
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    @TestDataMaker(TestDataMaker.CLEAN_GITFLOW)
    def test_CleanGitflow(self):
        self.assertRaises(
            VersionFlowChecker.NoBumpVersion,
            self.handler.process)

    @TestDataMaker(TestDataMaker.JUST_BUMP)
    def test_JustBump(self):
        self.assertRaises(
            VersionFlowChecker.NoRepo,
            self.handler.process)

    @TestDataMaker(TestDataMaker.EMPTY_GIT_AND_BUMP)
    def test_EmptyGitAndBump(self):
        self.assertRaises(
            VersionFlowChecker.NoGitFlow,
            self.handler.process)

    @TestDataMaker(TestDataMaker.GIT_AND_DIRTY_BUMP)
    def test_GitAndDirtyBump(self):
        self.assertRaises(
            VersionFlowChecker.DirtyRepo,
            self.handler.process)

    @TestDataMaker(TestDataMaker.GIT_AND_BUMP)
    def test_GitAndBump(self):
        self.assertRaises(
            VersionFlowChecker.NoGitFlow,
            self.handler.process)

    @TestDataMaker(TestDataMaker.EMPTY_GITFLOW_AND_BUMP)
    def test_EmptyGitFlowAndBump(self):
        self.assertRaises(
            VersionFlowChecker.BumpNotInGit,
            self.handler.process)

    @TestDataMaker(TestDataMaker.GITFLOW_AND_DIRTY_BUMP)
    def test_GitFlowAndDirtyBump(self):
        self.assertRaises(
            VersionFlowChecker.DirtyRepo,
            self.handler.process)

    @TestDataMaker(TestDataMaker.GITFLOW_AND_BUMP)
    def test_GitFlowAndBump(self):
        self.assertRaises(
            VersionFlowChecker.NoVersionTags,
            self.handler.process)

    @TestDataMaker(TestDataMaker.EMPTY_BAD_TAG_AND_BUMP)
    def test_EmptyBadTagAndBump(self):
        self.assertRaises(
            VersionFlowChecker.BadVersionTags,
            self.handler.process)

    @TestDataMaker(TestDataMaker.BAD_TAG_AND_BUMP)
    def test_BadTagAndBump(self):
        self.assertRaises(
            VersionFlowChecker.BadVersionTags,
            self.handler.process)

    @TestDataMaker(TestDataMaker.GOOD_REPO)
    def test_GoodRepo(self):
        vf_repo = self.handler.process()
        self.assertEqual(
            vf_repo.bv_wrapper.current_version,
            TestDataMaker.GOOD_VERSION)


@TestDataMaker.make_state_checker
class Test_VersionFlowChecker_Initialise(unittest.TestCase):
    def setUp(self):
        self.runner = click.testing.CliRunner()
        self.fs = setup_with_context_manager(
            self, self.runner.isolated_filesystem())
        self.handler = VersionFlowChecker.from_config(config=Config(
            os.getcwd(), bumpversion_config="setup.cfg"), create=True)

    @TestDataMaker(TestDataMaker.NOTHING)
    def test_InitNoGit(self):
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.0")

    @TestDataMaker(TestDataMaker.JUST_GIT)
    def test_InitJustGit(self):
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version,
                         "0.0.0")

    @TestDataMaker(TestDataMaker.DIRTY_EMPTY_GIT_REPO)
    def test_InitDirtyEmptyGit(self):
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    @TestDataMaker(TestDataMaker.DIRTY_GIT_REPO)
    def test_InitDirtyGit(self):
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    @TestDataMaker(TestDataMaker.CLEAN_GIT_REPO)
    def test_InitCleanGit(self):
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.0")

    @TestDataMaker(TestDataMaker.CLEAN_EMPTY_GITFLOW)
    def test_InitEmptyGitflow(self):
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version,
                         "0.0.0")

    @TestDataMaker(TestDataMaker.DIRTY_EMPTY_GITFLOW_REPO)
    def test_InitDirtyEmptyGitflow(self):
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    @TestDataMaker(TestDataMaker.DIRTY_GITFLOW_REPO)
    def test_InitDirtyGitflow(self):
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    @TestDataMaker(TestDataMaker.CLEAN_GITFLOW)
    def test_InitCleanGitflow(self):
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.0")

    @TestDataMaker(TestDataMaker.JUST_BUMP)
    def test_InitJustBump(self):
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version,
                         TestDataMaker.GOOD_VERSION)

    @TestDataMaker(TestDataMaker.EMPTY_GIT_AND_BUMP)
    def test_InitEmptyGitAndBump(self):
        vf_repo = self.handler.process()
        self.assertEqual(
            vf_repo.bv_wrapper.current_version,
            TestDataMaker.GOOD_VERSION)

    @TestDataMaker(TestDataMaker.GIT_AND_DIRTY_BUMP)
    def test_InitGitAndDirtyBump(self):
        self.assertRaises(
            VersionFlowChecker.DirtyRepo,
            self.handler.process)

    @TestDataMaker(TestDataMaker.GIT_AND_BUMP)
    def test_InitGitAndBump(self):
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version,
                         TestDataMaker.GOOD_VERSION)

    @TestDataMaker(TestDataMaker.EMPTY_GITFLOW_AND_BUMP)
    def test_InitEmptyGitFlowAndBump(self):
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version,
                         TestDataMaker.GOOD_VERSION)

    @TestDataMaker(TestDataMaker.GITFLOW_AND_DIRTY_BUMP)
    def test_InitGitFlowAndDirtyBump(self):
        self.assertRaises(
            VersionFlowChecker.DirtyRepo,
            self.handler.process)

    @TestDataMaker(TestDataMaker.GITFLOW_AND_BUMP)
    def test_InitGitFlowAndBump(self):
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version,
                         TestDataMaker.GOOD_VERSION)

    @TestDataMaker(TestDataMaker.EMPTY_BAD_TAG_AND_BUMP)
    def test_InitEmptyBadTagAndBump(self):
        self.assertRaises(
            VersionFlowChecker.BadVersionTags,
            self.handler.process)

    @TestDataMaker(TestDataMaker.BAD_TAG_AND_BUMP)
    def test_InitBadTagAndBump(self):
        self.assertRaises(
            VersionFlowChecker.BadVersionTags,
            self.handler.process)

    @TestDataMaker(TestDataMaker.GOOD_REPO)
    def test_InitRepoAlreadyGood(self):
        vf_repo = self.handler.process()
        self.assertEqual(
            vf_repo.bv_wrapper.current_version,
            TestDataMaker.GOOD_VERSION)


class Test_VersionFlowRepo(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_process_action(self):
        pass


class TestCommandLine(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testCheck(self):
        pass

    def testInit(self):
        pass

    def testPatch(self):
        pass

    def testMinor(self):
        pass

    def testMajor(self):
        pass


if __name__ == "__main__":
    unittest.main()
