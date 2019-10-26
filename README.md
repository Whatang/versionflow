# versionflow

Automatic Semantic Versioning with Git Flow.

The point of versionflow is to enhance the [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/) branching model with an automated approach to [semantic versioning](https://semver.org/) of your software's releases. It installs a command line utility which you can use to check your repo's status, initialise the versionflow approach, and create semantically versioned releases.

## Installation

`versionflow` is a Python package. With a Python installation, do

    pip install versionflow

to install it.

## Getting Started With versionflow

`versionflow` works on two assumptions: that you will use the Git Flow methodology for development, and that you want to tag commits on the `master` branch of your project with semantic version numbers.

To get started with a project, you need to initialise it to use Git and Git Flow, and have a versionflow configuration file. You **could** do all that by hand, but luckily `versionflow` can do it for you. Just run

    versionflow init

in youir project's root directory and `versionflow` will create a git repo, initialise it with Git Flow branches, create the config file, and tag the first (empty) commit as  "0.0.0".

Now we do some work and commit it to our development branch, and we're ready to create our first release! Let's first check that we're ready:

    versionflow check

This will run through a few checks to make sure we're ready to start a release:

1. We're in a git repo, initialised for Git Flow.
2. The repo is clean: there are no tracked files with uncommitted changes.
3. We have a versionflow config file, and the version number in it is consistent with the last version tag.

These checks all get done before you can actually perform a versionflow release & bump action, but it's good to be able to see your current status without the possibility of affecting anything.

Now, let's do our release! It's our first one, so we'll say it's a minor release, i.e. we're going to release v0.1.0.

    versionflow minor

That's it! versionflow will do the same checks as above, and if everything is OK it will perform a few actions:

1. Create a "Release/0.1.0" branch from the current development commit.
2. Update the version number in the versionflow configuration file from 0.0.0 to 0.1.0.
3. Merging "Release/0.1.0/ into master, and remove the release branch.
4. Tag the merge commit on master as "0.1.0".
5. Merge the master branch into develop, so that the latest tag and version number in there is 0.1.0.

So now you'll have a nice, consistent repo: the master branch will contain your latest release, tagged to the appropriate version number.

## Commands

* **check**
Check whether this directory is correctly initialised for versionflow, and ready to bump a version number: is it a git repo; is the repo clean (i.e. not dirty); does it have the standard Git Flow branches; does it have a versionflow config file; does it have a semantic version tag on the `master` branch matching the versionflow config?
* **init**
Initialise this directory as a versionflow project: create a git repo (if there isn't already one); set up the Git Flow branches (if they don't already exist); and create a versionflow config file (if it does not exist).
* **major**
Create a release of this project from the latest commit on `development` with the major version number bumped.
* **minor**
Create a release of this project from the latest commit on `development` with the minor version number bumped.
* **patch**
Create a release of this project from the latest commit on `development` with the patch version number bumped.

### Common Options

All the commands described above take the following options:

* --repo-dir PATH
Use the given PATH as the root of the versionflow repo. Defaults to the current directory.
* --config FILE
Use the given FILE as the versionflow configuration file. Defaults to `.versionflow`.
* --version
Print the current version of versionflow, and exit.
* --help
Print a help message

## Development

To create an environment in which to develop `versionflow`, clone the git repository and create a Python virtual environment using virtualenv. Then in the cloned repo, using the virtual environment, do

    pip -r requirements-dev.txt

This will install all the Python modules needed for developing versionflow.

### Testing

It is a good idea to create different testing virtual envs for versionflow as well as your dev environment. This will ensure that the package is configured to install properly via the configuration in `setup.cfg`, and that you don't have a hidden dependency on something installed in your dev environment.

To install your development version of versionflow in a testing virtual env, activate it, then do

    pip install -e .

in your local copy of the versionflow repo. Now as you work on it your latest changes will always be available in the virtual environment.

## Acknowledgements

`versionflow` uses:

* [setuptools_scm](https://pypi.org/project/setuptools-scm/) to find version numbers from commit tags;
* [nu-gitflow](https://github.com/chassing/gitflow/) to perform Git Flow actions;
* [bump2version](https://pypi.org/project/bump2version/) to increment version numbers;
* and [gitpython](https://github.com/gitpython-developers/GitPython) to perform miscellaneous git actions.
