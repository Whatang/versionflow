import unittest
import click
import click.testing
import os
import git
import gitflow.core
from versionflow import RepoStatusHandler, Config


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
            r = git.Repo.init()
        elif index == 1:
            # Make a dirty repo
            with open("test", "w") as handle:
                print >> handle, "test"
            r.index.add(["test"])
        elif index == 2:
            # Commit so the repo is clean
            r.index.commit("Initial commit")
        elif index == 3:
            # Initialize git flow
            gf = gitflow.core.GitFlow()
            gf.init()
        elif index == 4:
            # Add bumpversion config
            with open("setup.cfg", "w") as handle:
                print >> handle, "[bumpversion]"
                print >> handle, "current_version=0.0.2"
        elif index == 5:
            # Add non-matching tag
            gf.tag("0.0.1", "HEAD")
        elif index == 6:
            # Remove non-matching tag, add matching version tag
            gf.repo.git.tag("-d", "0.0.1")
            gf.tag("0.0.2", "HEAD")


class TestRepoStatusHandler_Check(unittest.TestCase):
    def setUp(self):
        self.runner = click.testing.CliRunner()
        self.fs = setup_with_context_manager(
            self, self.runner.isolated_filesystem())
        self.handler = RepoStatusHandler.from_config(config=Config(
            os.getcwd(), bumpversion_config="setup.cfg"), create=False)

    def test_NoGit(self):
        make_test_data(-1)
        self.assertRaises(RepoStatusHandler.NoRepo, self.handler.process)

    def test_DirtyGit(self):
        make_test_data(1)
        self.assertRaises(RepoStatusHandler.DirtyRepo, self.handler.process)

    def test_NoGitFlow(self):
        make_test_data(2)
        self.assertRaises(RepoStatusHandler.NoGitFlow, self.handler.process)

    def test_NoBumpVersion(self):
        make_test_data(3)
        self.assertRaises(
            RepoStatusHandler.BadBumpVersion,
            self.handler.process)

    def test_NoTags(self):
        make_test_data(4)
        self.assertRaises(
            RepoStatusHandler.NoVersionTags,
            self.handler.process)

    def test_BadTags(self):
        make_test_data(5)
        self.assertRaises(
            RepoStatusHandler.BadVersionTags,
            self.handler.process)

    def test_GoodRepo(self):
        make_test_data(6)
        self.handler.process()


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
