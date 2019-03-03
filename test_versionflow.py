import unittest
import click
import click.testing
import os
import git
import gitflow.core
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


def make_test_data(stage):
    for index in xrange(0, stage + 1):
        if index == 0:
            # Create git repo
            repo = git.Repo.init()
        elif index == 1:
            # Make a dirty repo
            with open("test", "w") as handle:
                print >> handle, "test"
            repo.index.add(["test"])
        elif index == 2:
            # Commit so the repo is clean
            repo.index.commit("Initial commit")
        elif index == 3:
            # Initialize git flow
            gf_wrapper = gitflow.core.GitFlow()
            gf_wrapper.init()
        elif index == 4:
            # Add bumpversion config
            with open("setup.cfg", "w") as handle:
                print >> handle, "[bumpversion]"
                print >> handle, "current_version=1.0.2"
        elif index == 5:
            # Add non-matching tag
            gf_wrapper.tag("0.0.1", "HEAD")
        elif index == 6:
            # Remove non-matching tag, add matching version tag
            gf_wrapper.repo.git.tag("-d", "0.0.1")
            gf_wrapper.tag("1.0.2", "HEAD")


class TestVersionFlowChecker_Check(unittest.TestCase):
    def setUp(self):
        self.runner = click.testing.CliRunner()
        self.fs = setup_with_context_manager(
            self, self.runner.isolated_filesystem())
        self.handler = VersionFlowChecker.from_config(config=Config(
            os.getcwd(), bumpversion_config="setup.cfg"), create=False)

    def test_NoGit(self):
        make_test_data(-1)
        self.assertRaises(VersionFlowChecker.NoRepo, self.handler.process)

    def test_DirtyGit(self):
        make_test_data(1)
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    def test_NoGitFlow(self):
        make_test_data(2)
        self.assertRaises(VersionFlowChecker.NoGitFlow, self.handler.process)

    def test_NoBumpVersion(self):
        make_test_data(3)
        self.assertRaises(
            VersionFlowChecker.BadBumpVersion,
            self.handler.process)

    def test_NoTags(self):
        make_test_data(4)
        self.assertRaises(
            VersionFlowChecker.NoVersionTags,
            self.handler.process)

    def test_BadTags(self):
        make_test_data(5)
        self.assertRaises(
            VersionFlowChecker.BadVersionTags,
            self.handler.process)

    def test_GoodRepo(self):
        make_test_data(6)
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version, "1.0.2")


class Test_VersionFlowChecker_Initialise(unittest.TestCase):
    def setUp(self):
        self.runner = click.testing.CliRunner()
        self.fs = setup_with_context_manager(
            self, self.runner.isolated_filesystem())
        self.handler = VersionFlowChecker.from_config(config=Config(
            os.getcwd(), bumpversion_config="setup.cfg"), create=True)

    def test_InitNoGit(self):
        make_test_data(-1)
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.1")

    def test_InitDirtyGit(self):
        make_test_data(1)
        self.assertRaises(VersionFlowChecker.DirtyRepo, self.handler.process)

    def test_InitNoGitFlow(self):
        make_test_data(2)
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.1")

    def test_InitNoBumpVersion(self):
        make_test_data(3)
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version, "0.0.1")

    def test_InitNoTags(self):
        make_test_data(4)
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version, "1.0.2")

    def test_InitBadTags(self):
        make_test_data(5)
        self.assertRaises(
            VersionFlowChecker.BadVersionTags,
            self.handler.process)

    def test_InitRepoAlreadyGood(self):
        make_test_data(6)
        vf_repo = self.handler.process()
        self.assertEqual(vf_repo.bv_wrapper.current_version,
                         "1.0.2")


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
